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


import csv
import argparse
import os.path
import pprint
import collections

from . import database
from . import matcher

class MatcherOutput:

    def __init__(self, rsdb, dir='.'):
        self._rsdb = rsdb
        self._dir = dir

    def create_assignments_csv(self, filename='assignments.csv'):
        path = os.path.join(self._dir, filename)
        print('Creating assignment CSV output: %s' % path)
        self._rsdb.init_catalog()
        rows = [[
            'School', 'Day', 'Time',
            'Teacher Email', 'Teacher First', 'Teacher Last',
            'Student ID', 'Student First', 'Student Last',
            'Grade', 'Gender', 'Reading Level',
            'Volunteer ID', 'Coach Email', 'Coach First', 'Coach Last',
            'Manual']]
        for assign in self._rsdb.assignments:
            day, slot, t_guid, s_guid, c_guid = assign
            day_str = self._rsdb.metadata.day_to_str(day)
            time_str = self._rsdb.metadata.slot_to_time(slot)
            teacher = self._rsdb.catalog.get_obj(t_guid)
            student = self._rsdb.catalog.get_obj(s_guid)
            coach = self._rsdb.catalog.get_obj(c_guid)
            school = self._rsdb.find_school(teacher)
            manual = self._rsdb.is_manual_assignment(assign)
            rows.append([
                school.name,
                day_str,
                time_str,
                teacher.email,
                teacher.first,
                teacher.last,
                student.student_id,
                student.first,
                student.last,
                student.grade,
                student.gender,
                student.level,
                coach.vid,
                coach.email,
                coach.first,
                coach.last,
                manual])

        with open(path, 'w', newline='') as csv_file:
            writer = csv.writer(csv_file)
            for row in rows:
                writer.writerow(row)
                
    def create_report(self, filename='report.txt'):
        reports = []
        matcher.Traversal.SLOTS_PER_ASSIGNMENT = self._rsdb.metadata.slots_per_assignment
        schools = sorted(self._rsdb.schools, key=lambda x: x.name)
        for school in schools:
            school_coaches = []
            for coach in self._rsdb.coaches:
                match1 = school.name in coach.schools
                match2 = 'Greatest Need' in coach.schools
                if match1 or match2:
                    school_coaches.append(coach)
            match = matcher.SchoolMatcher(school, school_coaches)
            match.find_cycles()
            root = matcher.Traversal(school, school_coaches)
            _, traversals = match.apply_assignments([root], self._rsdb.assignments)
            root = traversals[0]
            reports.append(TraversalReport(root))

        with open(filename, 'w') as out_file:
            for report in reports:
                out_file.write('[%s]\n' % report.traversal.school.name)
                for key, val in report.dict.items():
                    if isinstance(val, float):
                        val = '%0.02f' % val
                    out_file.write('%s=%s\n' % (key, val))
                out_file.write('\n')

    def create_school_calendars(self):
        school_assigns = {x.name: [] for x in self._rsdb.schools}
        for assign in self._rsdb.assignments:
            teacher = self._rsdb.catalog.get_obj(assign[2])
            school = self._rsdb.find_school(teacher)
            school_assigns[school.name].append(assign)

        for school_name, assigns in school_assigns.items():
            school = None
            teacher_to_row = {}
            for curr_school in self._rsdb.schools:
                if school_name == curr_school.name:
                    school = curr_school
                    break
            def grade_val(teacher_obj):
                if teacher_obj.grade == 'K':
                    return 0
                return int(teacher_obj.grade)
            row_i = 0
            for teacher in sorted(school.teachers, key=grade_val):
                teacher_to_row[teacher.guid] = row_i
                row_i += 1
            for assign in assigns:
                day, slot, t_guid, s_guid, c_guid = assign
                day_str = self._rsdb.metadata.day_to_str(day)
                time_str = self._rsdb.metadata.slot_to_time(slot)
                teacher = self._rsdb.catalog.get_obj(t_guid)
                student = self._rsdb.catalog.get_obj(s_guid)
                coach = self._rsdb.catalog.get_obj(c_guid)
                school = self._rsdb.find_school(teacher)


class TraversalReport:
    def __init__(self, trav):
        self.traversal = trav
        trav.reset_score()
        self.num_assigned = len(trav.assigned_students)
        self.num_unassigned = len(trav.unassigned_students)
        self.total_students = self.num_assigned + self.num_unassigned
        self.assign_percent = self.num_assigned / self.total_students * 100
        self.unassigned_percent = self.num_unassigned / self.total_students * 100
        self.total_teachers = len(trav.school.teachers)
        self.unassigned_teachers = trav.score[1]
        self.assigned_teachers = self.total_teachers - self.unassigned_teachers
        self.coaches_first = []
        self.coaches_second = []
        self.coaches_greatest = []
        for coach in trav.coaches:
            if trav.school.name == coach.schools[0]:
                self.coaches_first.append(coach)
            if trav.school.name == coach.schools[1]:
                self.coaches_second.append(coach)
            if 'Greatest Need' in coach.schools:
                self.coaches_greatest.append(coach)
        
        self.dict = collections.OrderedDict([
            ('Students.Total', self.total_students),
            ('Students.Assigned', self.num_assigned),
            ('Students.Assigned.Percent', self.assign_percent),
            ('Students.Unassigned', self.num_unassigned),
            ('Teachers.Total', self.total_teachers),
            ('Teachers.Assigned', self.assigned_teachers),
            ('Teachers.Unassigned', self.unassigned_teachers),
            ('Coaches.Total', len(trav.coaches))])
        coach_types = [
            ('FirstChoice', self.coaches_first),
            ('SecondChoice', self.coaches_second),
            ('GreatestNeed', self.coaches_greatest)]
        for type, coach_list in coach_types:
            self.dict['Coaches.%s.Total' % type] = len(coach_list)
            assigned = []
            assigned_days_remaining = 0
            unassigned = []
            unassigned_days_remaining = 0
            for coach in coach_list:
                found = False
                for assign in trav.assignments:
                    if coach.guid in assign:
                        found = True
                        break
                if found:
                    assigned.append(coach)
                    assigned_days_remaining += trav.coach_day_count[coach.guid]
                else:
                    unassigned.append(coach)
                    unassigned_days_remaining += trav.coach_day_count[coach.guid]
            self.dict['Coaches.%s.Assigned' % type] = len(assigned)
            self.dict['Coaches.%s.Assigned.DaysRemaining' % type] = assigned_days_remaining
            self.dict['Coaches.%s.Unassigned' % type] = len(unassigned)
            self.dict['Coaches.%s.Unassigned.DaysRemaining' % type] = unassigned_days_remaining


def create_school_calendar(path, school, assignments):
    num_days = len(school.students[0].schedule)
    num_slots = len(school.students[0].schedule[0])
    calendar = []
    teacher_schedules = {}
    coach_schedules = {}
    email_to_guid = dict([(x.email, x.guid) for x in school.teachers])
    teacher_keys = [(guid, email) for email, guid in email_to_guid.items()]
    teacher_lookup = dict(teacher_keys)

    for student in school.students:
        if student.teacher not in teacher_schedules:
            teacher_schedules[student.teacher] = [x[:] for x in student.schedule]
        else:
            schedule = teacher_schedules[student.teacher]
            for day_i in range(num_days):
                for slot_i in range(num_slots):
                    schedule[day_i][slot_i] |= student.schedule[day_i][slot_i]

    for day_i, slot_i, teacher_id, student_id, coach_id in assignments:
        schedule = teacher_schedules[teacher_lookup[teacher_id]]
        schedule[day_i][slot_i] = 2

    header_row = ['teacher', 'grade']
    for day_i in range(num_days):
        for slot_i in range(num_slots):
            header_row.append('%s@%s' % (day_i, slot_i))
    calendar.append(header_row)

    for teacher_id, teacher_email in sorted(teacher_keys):
        for teacher in school.teachers:
            if teacher.guid == teacher_id:
                grade = teacher.grade
        row = [teacher_id, grade]
        schedule = teacher_schedules[teacher_email]
        for day_i in range(num_days):
            row += schedule[day_i]
        calendar.append(row)

    with open(path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        for row in calendar:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'db_path', default='rsdb.json')
    args = parser.parse_args()

    rsdb = database.RSDatabase.from_path(args.db_path)
    rsdb.init_catalog()

    match_out = MatcherOutput(rsdb)
    match_out.create_assignments_csv()
    match_out.create_report()


if __name__ == '__main__':
    main()