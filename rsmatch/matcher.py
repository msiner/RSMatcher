"""
Copyright (c) 2019 Mark Siner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import collections
import random
from pprint import pprint
import argparse

import networkx

from . import database
from . import output


class Traversal: # pylint: disable=too-many-instance-attributes
    """A Traversal represents a possible solution.
    The solution space is a large tree of possibilities where each node represents
    a decision of whether to add a cycle or not.
    A traversal is "done" when no more cycles can be added due to one of the
    following reasons:
    1) All students have been assigned a coach
    2) All coaches have been assigned as many students as they agreed to accept
    3) All coaches have been assigned as many days as they agreed to accept
    """
    
    SLOTS_PER_ASSIGNMENT = None

    def __init__(self, school, coaches, parent=None):
        """Create a new Traversal or a child of an existing Traversal.

        Args:
            school: a SchoolAssignment object
            coaches: a list of coaches being assigned
            parent (optional): a Traversal object from which to copy state
        """
        self.school = school
        self.coaches = coaches
        self.done = False
        # This is a cached value, it should be accessed externally through
        # the score property.
        self._score = None
        if parent is None:
            # If there is no parent, create clean state
            # Keep track of how many students have been assigned to each coach
            self.coach_student_count = {
                x.guid:x.num_students - len(x.assignments) for x in coaches}

            # Keep track of how many days each coach has been assigned
            self.coach_day_count = {
                x.guid:x.num_days - len(x.assigned_days) for x in coaches}

            # Keep these tallies for efficient checking vs the dict and set lookups
            self.days_remaining = sum([x for x in self.coach_day_count.values()])
            self.students_remaining = sum([x for x in self.coach_student_count.values()])

            # A dict of sets such that coach_days[coach_guid] is a set of day_i values
            # representing each day the coach has been given an assignment.
            self.coach_days = {x.guid:x.assigned_days.copy() for x in coaches}

            # Add students to the unassigned and assigned pools
            self.unassigned_students = {
                x.guid for x in school.students if not x.assigned}
            self.assigned_students = {
                x.guid for x in school.students if x.assigned}

            # Keep track of all (day_i, slot_i, teacher_guid) nodes that have
            # been used for the entire solution.
            self.nodes_used = set()
            self.num_cycles = 0

            # The actual list of assignments
            self.assignments = []
        else:
            # Take on the state of the parent
            self.coach_student_count = parent.coach_student_count.copy()
            self.coach_day_count = parent.coach_day_count.copy()
            self.days_remaining = parent.days_remaining
            self.students_remaining = parent.students_remaining
            # Need to do a deep copy since coach_days is a dict of sets
            self.coach_days = dict((x, y.copy()) for x, y in parent.coach_days.items())
            self.unassigned_students = parent.unassigned_students.copy()
            self.assigned_students = parent.assigned_students.copy()
            self.nodes_used = parent.nodes_used.copy()
            self.num_cycles = parent.num_cycles
            self.assignments = parent.assignments.copy()

    def add_cycle(self, graph, cycle):
        """Attempt to add a cycle to this traversal and return the new
        traversal if it can be added.

        Args:
            graph: master graph used to look up students by time slot
            cycle: cycle to be added

        Returns:
            If the cycle can be added, returns a copy of this Traversal
            in which the cycle has been added to the solution.
            The cycle will not add anything new to this solution.
            If the cycle cannot be added, returns None.
        """
        result = None
        coach_guid = cycle[0]
        # Since each of the following checks takes some amount of work,
        # we will do them in a cascade.
        # The tree traversal is not meant to be brute force.
        # By refusing to follow invalid paths, we preemptively
        # prune the tree.
        days_remaining = self.coach_day_count[coach_guid]
        # RULE: Don't schedule a coach who can't take more days
        if days_remaining:
            cycle = cycle[1:]
            students_remaining = self.coach_student_count[coach_guid]
            # RULE: Don't schedule a coach who can't take more students
            if (len(cycle) // Traversal.SLOTS_PER_ASSIGNMENT) <= students_remaining:
                day_i = cycle[0][0]
                new_day = day_i not in self.coach_days[coach_guid]
                # RULE: Don't schedule a coach for multiple visits in the same day
                if new_day:
                    # Create a new child and attempt to add the cycle to
                    # the child. We do it to the child because if it can't
                    # be added, then we can just discard the child.
                    result = Traversal(self.school, self.coaches, parent=self)
                    result.num_cycles += 1
                    num_assignments = 0
                    for node_i in range(0, len(cycle), Traversal.SLOTS_PER_ASSIGNMENT):
                        node = cycle[node_i]
                        nodes = set(cycle[node_i:node_i + Traversal.SLOTS_PER_ASSIGNMENT])
                        # RULE: Don't schedule two coaches at the same time with the same teacher
                        if not nodes.intersection(result.nodes_used):
                            result.nodes_used = nodes.union(result.nodes_used)
                            node_students = graph.node[node]['students']
                            possible_students = set(node_students)
                            to_assign = None

                            # Make sure each student is available for the entire slot
                            for curr_node in nodes:
                                curr_students = set(graph.node[curr_node]['students'])
                                possible_students = possible_students.intersection(curr_students)

                            # Try to find a student to assign
                            for student_guid in node_students:
                                if student_guid in possible_students:
                                    if student_guid in result.unassigned_students:
                                        to_assign = student_guid
                                        break

                            if to_assign is not None:
                                # We found an unassigned student in the slot
                                result.unassigned_students.remove(to_assign)
                                result.assigned_students.add(to_assign)
                                result.coach_student_count[coach_guid] -= 1
                                result.students_remaining -= 1
                                assignment = (
                                    node[0],
                                    node[1],
                                    node[2],
                                    to_assign,
                                    coach_guid)
                                result.assignments.append(assignment)
                                num_assignments += 1
                    if num_assignments == (len(cycle) // Traversal.SLOTS_PER_ASSIGNMENT):
                        # The cycle was added successfully because all
                        # time slots yielded assignments.
                        result.coach_day_count[coach_guid] -= 1
                        result.days_remaining -= 1
                        result.coach_days[coach_guid].add(day_i)
                    else:
                        # We could not find valid assignments for the
                        # entire cycle. Throw away the new Traversal because
                        # if the cycle has any sub-cycles, they will be in
                        # the entire list of cycles.
                        # RULE: A coaches visit to a school will not have empty time slots
                        result = None

        if (
                (self.days_remaining == 0) or
                (self.students_remaining == 0) or
                (not self.unassigned_students)):
            # Nothing else can be added to this solution, we're done
            self.done = True
            # Release state memory
            self.coach_student_count = None
            self.coach_day_count = None
            self.coach_days = None
            self.nodes_used = None

        # Returns either new Traversal or None
        return result

    def reset_score(self):
        """Remove any cached score to force a recalculation on the
        next access of score.
        """
        self._score = None

    @property
    def score(self):
        """Return a tuple for sorting solutions
        For efficiency, the score is only calculated when requested, but
        it is cached for all subsequent accesses.
        This means that multiple accesses of the score during a sort
        operation are more efficient.
        If a new sort needs to be done, call reset_score() first on all
        solutions being sorted.
        This will remove the cached score and it will be recalculated on
        the next request.
        """
        if self._score is None:
            # Count unassigned teachers
            unassigned_teachers = {x.guid for x in self.school.teachers}
            for assignment in self.assignments:
                teacher_guid = assignment[2]
                if teacher_guid in unassigned_teachers:
                    unassigned_teachers.remove(teacher_guid)
            # Count slot overlaps (will not be same teacher)
            slots = set()
            slot_overlaps = 0
            for assignment in self.assignments:
                slot = (assignment[0], assignment[1])
                if slot in slots:
                    slot_overlaps += 1
                else:
                    slots.add(slot)
            # RULE: Solution scoring priorities:
            # RULE: 1. Minimize unassigned students
            # RULE: 2. Minimize unassigned teachers
            # RULE: 3. Minimize simultaneous visits to the same school
            # RULE: 4. Minimize number of days coaches are still available
            self._score = (
                len(self.unassigned_students),
                len(unassigned_teachers),
                slot_overlaps,
                self.days_remaining)
        return self._score


class SchoolMatcher:
    """This class represents and encapsulates the assignment
    process for a single school and pool of coaches.
    """

    def __init__(self, school, coaches, callback=None):
        """Create a new SchoolAssignment.

        Args:
            school: School object
            coaches: list of Coach objects
        """
        self.school = school
        self.coaches = coaches
        self.callback = None
        self.graph = None
        self.cycles = []
        self.solution = None
        self.progress = 0

    def find_cycles(self):
        """Find all of the cycles"""
        students = self.school.students[:]

        # RULE: Remove any student bias by randomizing order before assignment
        random.shuffle(students)

        # We need to build a graph where each node is (day_i, slot_i, teacher_guid)
        # First we need to find all valid such combinations.
        # For efficiency later we group these first by (day_i, slot_i)
        # such that nodes[(day_i, slot_i)] = {coach_guid: [student_guid, ...], ...}
        teachers_by_email = {x.email:x for x in self.school.teachers}
        teachers_by_guid = {x.guid:x for x in self.school.teachers}
        nodes = {}
        num_days = len(students[0].schedule)
        num_slots = len(students[0].schedule[0])
        for day_i in range(num_days):
            for slot_i in range(num_slots):
                for student in students:
                    if student.schedule[day_i][slot_i] == 1:
                        teacher_guid = teachers_by_email[student.teacher].guid
                        key = (day_i, slot_i)
                        if key not in nodes:
                            nodes[key] = {}
                        if teacher_guid not in nodes[key]:
                            nodes[key][teacher_guid] = []
                        nodes[key][teacher_guid].append(student.guid)

        # Now we build the master graph.
        # Each node is identified by a (day_i, slot_i, teacher_guid) tuple.
        # Each node stores a list of student_guids that are available
        # at that time slot with that teacher.
        graph = networkx.DiGraph()
        self.graph = graph
        for key, node in nodes.items():
            for teacher_guid, node_students in node.items():
                node_key = (key[0], key[1], teacher_guid)
                graph.add_node(node_key, students=node_students)
        # The master graph only has directed edges such that:
        # (day_i, slot_i, teacher_guid) => (day_i, slot_i + 1, teacher_guid)
        # This means that following the edges can only follow
        # chronological order, only in the same day, and only with the same
        # teacher.
        for day_i in range(num_days):
            for slot_i in range(1, num_slots):
                key = (day_i, slot_i)
                if key in nodes:
                    slot_node = nodes[key]
                    for teacher_guid in slot_node:
                        node_key = (day_i, slot_i, teacher_guid)
                        prev_key = (day_i, slot_i - 1, teacher_guid)
                        graph.add_edge(prev_key, node_key)

        # Find all cycles one coach at a time.
        # This is done by copying the master graph and adding
        # a single node for the coach, but then adding directed
        # edges to and from each (day_i, slot_i, teacher_guid) node
        # that is valid for the coach.
        # Once that is done, each cycle must include a coach node and
        # a contiguous block of time with a single teacher.
        # A cycle cannot traverse the same node twice, so it is impossible
        # for the single coach node to be included twice.
        all_cycles = []
        for coach in self.coaches:
            coach_guid = coach.guid
            # create a copy of the master graph
            coach_graph = graph.copy()
            # add a single node to represent the coach
            coach_graph.add_node(coach_guid)
            grades = set(coach.grades)
            no_grade_pref = len(grades) == 0
            for day_i in range(num_days):
                for slot_i in range(num_slots):
                    if coach.schedule[day_i][slot_i] == 1:
                        slot_key = (day_i, slot_i)
                        if slot_key in nodes:
                            slot_node = nodes[slot_key]
                            for teacher_guid in slot_node:
                                teacher = teachers_by_guid[teacher_guid]
                                # RULE: A coach with no grade preference is assigned to any grade
                                # RULE: A coach is only assigned to a preferred grade
                                if no_grade_pref or (teacher.grade in grades):
                                    node_key = (day_i, slot_i, teacher_guid)
                                    # Add directed edge from coach to the slot
                                    coach_graph.add_edge(coach_guid, node_key)
                                    # Add directed edge from slot back to coach
                                    coach_graph.add_edge(node_key, coach_guid)

            # Get all of the cycles in the coach graph.
            # Each cycle represents a contiguous block of time a coach could
            # spend with students from a single teacher.
            cycles = list(networkx.simple_cycles(coach_graph))

            # Some cycles will be invalid.
            # Also, the cycles need to be reformatted.
            filtered_cycles = []
            for cycle in cycles:
                # Remove coach_guid from somewhere in the list
                cycle = [x for x in cycle if isinstance(x, tuple)]
                # Filter out any cycles that include more students than
                # the coach wants in total
                if (len(cycle) // Traversal.SLOTS_PER_ASSIGNMENT) <= coach.num_students:
                    if (len(cycle) % Traversal.SLOTS_PER_ASSIGNMENT) == 0:
                        # The cycle might "start" from the middle,
                        # so we sort the (day, slot, teacher) tuples so the
                        # first time slot is at index 0 and the rest are in order.
                        # Tuples of ints sort correctly.
                        cycle.sort()
                        # Add the coach_guid back in at index 0 for bookkeeping
                        cycle.insert(0, coach_guid)
                        filtered_cycles.append(cycle)

            # RULE: Prefer the longest possible visits each day
            filtered_cycles.sort(key=len)
            #filtered_cycles.sort(key=lambda x: (len(x), x[1]))

            #with open('cycles\%s_cycles_%d.txt' % (coach_guid, SLOTS_PER_ASSIGNMENT), 'w') as out_file:
            #   for cycle in filtered_cycles:
            #        out_file.write('%s\n' % cycle)

            all_cycles.append(filtered_cycles)

        # Round-robin cycles by coach
        # This is less of a rule and more of a heuristic to explore more
        # possibilities faster.
        # If we don't do this, a coach with an extremely available schedule
        # might dominate the top of the list of cycles.
        cycles = []
        keep_adding = True
        while keep_adding:
            keep_adding = False
            for cycle_list in all_cycles:
                # Some coaches will have more cycles than others
                if cycle_list:
                    cycle = cycle_list.pop()
                    cycles.append(cycle)
                    keep_adding = True

        # Round-robin cycles by teacher
        # RULE: Remove teacher bias to distribute coaches to all teachers
        # First we need to group the cycles by teacher while retaining order.
        cycles_by_teacher = collections.OrderedDict()
        for cycle in cycles:
            # Last element in the last cycle should be teacher_guid
            teacher_guid = cycle[-1][-1]
            if teacher_guid not in cycles_by_teacher:
                cycles_by_teacher[teacher_guid] = []
            cycles_by_teacher[teacher_guid].append(cycle)
        # Go through all cycles by teacher and rebuilding the cycles list.
        cycles = []
        keep_adding = True
        while keep_adding:
            keep_adding = False
            for _, cycle_list in cycles_by_teacher.items():
                # Some teachers will have more cycles than others
                if cycle_list:
                    cycle = cycle_list.pop(0)
                    cycles.append(cycle)
                    keep_adding = True

        self.cycles = cycles

        # TODO: remove debugging code or add to DB
        #with open('cycles.txt', 'w') as cycles_file:
        #    for cycle in self.cycles:
        #        cycles_file.write('%s\n' % cycle)
        
    def notify(self, progress=None, status=None):
        if progress is not None:
            self.progress = progress
        if status is not None:
            self.status = status
        print('%.02f%%: %s' % (self.progress * 100, self.status))
        if self.callback is not None:
            self.callback(self)

    def find_solutions(self):
        """Search for the best solution.
        The best solution is stored in the 'solution' attribute'
        """
        # Create the root of the tree.
        # All Traversals will be descended from this one.
        self.notify(0, 'Matching on %s' % self.school.name)
        
        root = Traversal(self.school, self.coaches)
        traversals = [root]
        cycles = self.cycles
        
        cycles_remaining = len(cycles)
        total_possible = 2**cycles_remaining
        eliminated = 0
        
        print('Total cycles: %d' % len(cycles))
        
        finished = []
        max_finished = 100000
        max_unfinished = 200000

        num_cycles = 0
        for cycle in cycles:
            num_cycles += 1
            expected_size = 2**num_cycles
            eliminated = expected_size - len(traversals)
            self.notify(
                num_cycles / len(cycles),#eliminated / total_possible,
                '%d finished, %d unfinished' % (len(finished), len(traversals)))
            #print(len(finished), len(traversals), cycle)
            #print(cycles_remaining, eliminated)
            if len(finished) >= max_finished:
                break
            if len(traversals) >= max_unfinished:
                # We have too many Traversals.
                # Score, sort, and cull
                print('Culling lowest scoring solutions')
                traversals.sort(key=lambda x: x.score)
                traversals = traversals[:max_finished]
                for traversal in traversals:
                    # The score gets cached, so we need to reset it
                    traversal.reset_score()

            # Collect all non-done and new child Traversals in this list.
            new_traversals = []
            for traversal in traversals:
                new_traversal = traversal.add_cycle(self.graph, cycle)
                if new_traversal is not None:
                    new_traversals.append(new_traversal)
                    
                if traversal.done:
                    # If a Traversal is done, put it to the side
                    finished.append(traversal)
                else:
                    new_traversals.append(traversal)
            # Swap traversals to essential remove any finished
            # Traversals from consideration.
            traversals = new_traversals

        # It is possible that too few or none finished before
        # exhausting the search space
        if len(finished) < max_finished:
            # If we didn't hit max_finished, score and sort the unfinished
            # Traversals and add them to finished for final consideration.
            traversals.sort(key=lambda x: x.score)
            finished += traversals[:max_finished - len(finished)]
        # Throw away unneeded state memory
        del traversals

        # Final score and sort
        self.notify(status='Scoring final results')
        finished.sort(key=lambda x: x.score)
        print('Top 10 results:')
        for traversal in finished[:10]:
            print(traversal.score)
        print('New Assignments:')
        pprint(finished[0].assignments)
        # Take the best Traversal as the solution
        self.solution = finished[0]
        self.notify(1, 'Matching complete for %s' % self.school.name)


def do_match(database_path, school=None, first=True, second=False, greatest=False):
    rsdb = database.RSDatabase.from_path(database_path)

    rsdb.init_catalog()

    Traversal.SLOTS_PER_ASSIGNMENT = rsdb.metadata.slots_per_assignment

    for school_obj in rsdb.schools:
        if school in (None, school_obj.name):
            print('Processing %s' % school_obj.name)
            school_coaches = []
            for coach in rsdb.coaches:
                match1 = first and school_obj.name == coach.schools[0]
                match2 = second and school_obj.name == coach.schools[1]
                match3 = greatest and 'Greatest Need' in coach.schools
                if match1 or match2 or match3:
                    school_coaches.append(coach)
            matcher = SchoolMatcher(school_obj, school_coaches)
            matcher.find_cycles()
            matcher.find_solutions()
            for assign in matcher.solution.assignments:
                rsdb.check_assignment(assign)
            for assign in matcher.solution.assignments:
                rsdb.add_assignment(assign)

    rsdb.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--school', '-s', default=None, help='Name of school process')
    parser.add_argument(
        'db_path', default='rsdb.json')
    args = parser.parse_args()
    do_match(args.db_path, school=args.school)


if __name__ == '__main__':
    main()