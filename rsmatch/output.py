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
import collections

from . import database


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
            'Grade', 'Gender', 'ELL Student',
            'Volunteer ID', 'Coach Email', 'Coach First', 'Coach Last',
            'Timestamp']]
        for entry in self._rsdb.assignments:
            day, slot, t_guid, s_guid, c_guid = entry['assign']
            timestamp = entry['timestamp']
            if entry['manual']:
                timestamp = 'manual'
            day_str = self._rsdb.metadata.day_to_str(day)
            time_str = self._rsdb.metadata.slot_to_time(slot)
            teacher = self._rsdb.catalog.get_obj(t_guid)
            student = self._rsdb.catalog.get_obj(s_guid)
            coach = self._rsdb.catalog.get_obj(c_guid)
            school = self._rsdb.find_school(teacher)
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
                student.ell,
                coach.vid,
                coach.email,
                coach.first,
                coach.last,
                timestamp])

        with open(path, 'w', newline='') as csv_file:
            writer = csv.writer(csv_file)
            for row in rows:
                writer.writerow(row)
                
    def create_report(self, filename='report.txt'):
        reports = []
        schools = sorted(self._rsdb.schools, key=lambda x: x.name)
        for school in schools:
            report = SchoolResourceReport(self._rsdb, school)
            reports.append(report)

        with open(filename, 'w') as out_file:
            for report in reports:
                out_file.write('[%s]\n' % report.school.name)
                for key, val in report.dict.items():
                    if isinstance(val, float):
                        val = '%0.02f' % val
                    out_file.write('%s=%s\n' % (key, val))
                out_file.write('\n')


class SchoolResourceReport:
    def __init__(self, rsdb, school):
        self.school = school
        self.num_assigned = len(
            [x for x in school.students if x.assigned])
        self.num_unassigned = len(
            [x for x in school.students if not x.assigned])
        self.total_students = len(school.students)
        self.assign_percent = self.num_assigned / self.total_students * 100
        self.unassigned_percent = self.num_unassigned / self.total_students * 100
        self.total_teachers = len(school.teachers)
        self.assigned_teachers = len(
            {x.teacher for x in school.students if x.assigned})
        self.unassigned_teachers = self.total_teachers - self.assigned_teachers
        self.coaches_first = []
        self.coaches_second = []
        self.coaches_greatest = []
        for coach in rsdb.coaches:
            if school.name == coach.schools[0]:
                self.coaches_first.append(coach)
            if school.name == coach.schools[1]:
                self.coaches_second.append(coach)
            if 'Greatest Need' in coach.schools:
                self.coaches_greatest.append(coach)
        num_coaches = len(set(
            self.coaches_first +
            self.coaches_second +
            self.coaches_greatest))
        
        self.dict = collections.OrderedDict([
            ('Students.Total', self.total_students),
            ('Students.Assigned', self.num_assigned),
            ('Students.Assigned.Percent', self.assign_percent),
            ('Students.Unassigned', self.num_unassigned),
            ('Teachers.Total', self.total_teachers),
            ('Teachers.Assigned', self.assigned_teachers),
            ('Teachers.Unassigned', self.unassigned_teachers),
            ('Coaches.Total', num_coaches)])
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
                if coach.assignments:
                    assigned.append(coach)
                    assigned_days_remaining += (
                        coach.num_days - len(coach.assigned_days))
                else:
                    unassigned.append(coach)
                    unassigned_days_remaining += (
                        coach.num_days - len(coach.assigned_days))
            self.dict['Coaches.%s.Assigned' % type] = len(assigned)
            self.dict['Coaches.%s.Assigned.DaysRemaining' % type] = assigned_days_remaining
            self.dict['Coaches.%s.Unassigned' % type] = len(unassigned)
            self.dict['Coaches.%s.Unassigned.DaysRemaining' % type] = unassigned_days_remaining

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