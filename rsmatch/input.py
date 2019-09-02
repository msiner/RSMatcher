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


import os.path
import csv
import random
import argparse

from . import database


class ReferralRow:

    def __init__(self, row, meta):
        self.timestamp = row[0]
        self.teacher = database.Teacher()
        self.teacher.email = row[1].strip()
        self.school = row[4].strip()
        self.teacher.first = row[5].strip()
        self.teacher.last = row[6].strip()
        self.schedule = None

        if row[8].startswith('This is my first'):
            schedule = [[0] * meta.num_slots for _ in range(meta.num_days)]
            # lunch, recess1, recess2
            exclusions = row[9:11]
            days = row[12:12 + meta.num_days]
            for day_i in range(meta.num_days):
                day_times = days[day_i]
                day_times = day_times.split(',')
                for day_time in day_times:
                    day_time = day_time.strip()
                    if day_time.startswith('NONE'):
                        if len(day_times) > 1:
                            raise ValueError(
                                '%s selected along with other times' % day_time)
                    else:
                        start, stop = day_time.split('-')
                        start = meta.time_to_slot(start)
                        stop = meta.time_to_slot(stop)
                        for slot_i in range(start, stop):
                            schedule[day_i][slot_i] = 1
            
            # Handle these second to make sure they are excluded
            for exclusion in exclusions:
                if not exclusion.startswith('N/A'):
                    start, stop = exclusion.split('-')
                    start = meta.time_to_slot(start)
                    stop = meta.time_to_slot(stop)
                    for slot_i in range(start, stop):
                        for day_i in range(meta.num_days):
                            schedule[day_i][slot_i] = 0
            self.schedule = schedule
        
        self.students = []
        for col_i in range(12 + meta.num_days, len(row), 9):
            student_row = row[col_i:col_i + 9]
            student = database.Student()
            student.teacher = self.teacher.email
            student.student_id = student_row[0]
            student.first = student_row[1]
            student.last = student_row[2]
            student.grade = student_row[3]
            student.gender = student_row[4]
            student.level = student_row[5]
            self.teacher.grade = student.grade
            student.schedule = self.schedule
            # Skip gender, reading level, ELL, and race/ethnicity
            self.students.append(student)
            if student_row[-1].startswith('No'):
                break


class CoachRow:
    def __init__(self, row, meta):
        self.timestamp = row[0]
        self.email = row[1]
        self.vid = row[2]
        self.first = row[3]
        self.last = row[4]
        # Skip phone number
        self.school_prefs = row[9:11]
        self.grade_prefs = ['K', '1', '2', '3', '4', '5']
        
        self.num_students = int(row[12])
        self.num_days = int(row[13])

        availability = row[11].strip().split(',')
        day_lut = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4}
        schedule = [[0] * meta.num_slots for _ in range(meta.num_days)]
        for window in availability:
            day_str, time_str = window.strip().split(' ')
            day_i = day_lut[day_str]
            time_str = time_str.strip()
            start, stop = time_str.split('-')
            start = meta.time_to_slot(start)
            stop = meta.time_to_slot(stop)
            for slot_i in range(start, stop):
                schedule[day_i][slot_i] = 1
        self.schedule = schedule

    def to_db_obj(self):
        coach = database.Coach()
        coach.vid = self.vid
        coach.email = self.email
        coach.first = self.first
        coach.last = self.last
        coach.schools = self.school_prefs
        coach.grades = self.grade_prefs
        coach.num_students = self.num_students
        coach.num_days = self.num_days
        coach.schedule = self.schedule
        return coach


class AssignRow:

    def __init__(self, row, meta):
        self.school_name = row[0]
        self.day = meta.str_to_day(row[1])
        self.slot = meta.time_to_slot(row[2])
        self.teacher_email = row[3]
        self.teacher_first = row[4]
        self.teacher_last = row[5]
        self.student_id = row[6]
        self.first = row[7]
        self.last = row[8]
        self.grade = row[9]
        self.gender = row[10]
        self.reading_level = row[11]
        self.volunteer_id = row[12]
        self.coach_email = row[13]
        self.coach_first = row[14]
        self.coach_last = row[15]

    def to_db_obj(self, rsdb):
        school = None
        for curr_school in rsdb.schools:
            if curr_school.name == self.school_name:
                school = curr_school
                break
        if school is None:
            raise ValueError('Could not find school [%s]' % self.school_name)

        teacher = None
        teacher_tuple = (
            self.teacher_email, self.teacher_first, self.teacher_last)
        for curr_teacher in school.teachers:
            curr_tuple = (
                curr_teacher.email, curr_teacher.first, curr_teacher.last)
            if curr_tuple == teacher_tuple:
                teacher = curr_teacher
                break
        if teacher is None:
            raise ValueError('Could not find teacher [%s]' % (teacher_tuple,))

        student = None
        for curr_student in school.students:
            if curr_student.student_id == self.student_id:
                student = curr_student
                break
        if student is None:
            raise ValueError('Could not find student id=%s' % self.student_id)

        coach = None
        for curr_coach in rsdb.coaches:
            if curr_coach.vid == self.volunteer_id:
                coach = curr_coach
                break
        if coach is None:
            raise ValueError('Could not find coach vid=%s' % self.volunteer_id)

        return (self.day, self.slot, teacher.guid, student.guid, coach.guid)


def create_database(teacher_path, coach_path, assign_path, out_path):
    random.seed(0)
    meta = database.Metadata()
    out_dir = os.path.dirname(out_path)

    schools = {}
    teacher_schedules = {}
    invalid_referrals = []
    coaches = []
    invalid_coaches = []

    # Students
    with open(teacher_path, 'r') as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if row[0].startswith('Timestamp'):
                continue
            try:
                referral = ReferralRow(row, meta)
                if referral.school not in schools:
                    schools[referral.school] = database.School()
                    schools[referral.school].name = referral.school
                school = schools[referral.school]
                new_teacher = True
                for teacher in school.teachers:
                    if teacher.email == referral.teacher.email:
                        new_teacher = False
                        break
                if new_teacher:
                    school.teachers.append(referral.teacher)
                if referral.schedule:
                    teacher_schedules[referral.teacher.email] = referral.schedule
                else:
                    for student in referral.students:
                        student.schedule = teacher_schedules[student.teacher]
                for student in referral.students:
                    school.students.append(student)
            except Exception as ex:
                row.append(str(ex))
                invalid_referrals.append(row)

    # Coaches
    with open(coach_path, 'r') as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if row[0].startswith('Timestamp'):
                continue
            try:
                coach = CoachRow(row, meta)
                coaches.append(coach)
            except Exception as ex:
                row.append(str(ex))
                invalid_coaches.append(row)

    rsdb = database.RSDatabase()
    for school_name in sorted(schools.keys()):
        rsdb.schools.append(schools[school_name])

    for coach in coaches:
        rsdb.coaches.append(coach.to_db_obj())

    rsdb.init_catalog()
    rsdb.save(out_path)

    csv_path = os.path.join(out_dir, 'invalid_referrals.csv')
    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        print('Invalid referrals: %d' % len(invalid_referrals))
        for row in invalid_referrals:
            print(row)
            writer.writerow(row)
            

    csv_path = os.path.join(out_dir, 'invalid_coaches.csv')
    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        print('Invalid coaches: %d' % len(invalid_coaches))
        for row in invalid_coaches:
            print(row)
            writer.writerow(row)

    if assign_path:
        invalid_assigns = []
        assignments = []
        with open(assign_path, 'r') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                if row[0] == 'School':
                    continue
                try:
                    assign = AssignRow(row, meta)
                    assign_tuple = assign.to_db_obj(rsdb)
                    assignments.append(assign_tuple)
                except Exception as ex:
                    row.append(str(ex))
                    invalid_assigns.append(row)

        rsdb.assignments = assignments
        rsdb.save()

        csv_path = os.path.join(out_dir, 'invalid_assignments.csv')
        with open(csv_path, 'w', newline='') as csv_file:
            writer = csv.writer(csv_file)
            print('Invalid assignments: %d' % len(invalid_assigns))
            for row in invalid_assigns:
                print(row)
                writer.writerow(row)
        


def main():
    parser = argparse.ArgumentParser(
        description='Create assignment database using specified input')
    parser.add_argument(
        '-o', '--out', dest='out_path', default='database.json',
        help='path to referral output file')
    parser.add_argument(
        '-a', '--assign', dest='assign_path', default=None,
        help='path to assignments CSV file')
    parser.add_argument('referral_csv', help='path to referral CSV file')
    parser.add_argument('coach_csv', help='path to coach CSV file')

    args = parser.parse_args()
    create_database(
        args.referral_csv, args.coach_csv, args.assign_path, args.out_path)


if __name__ == '__main__':
    main()