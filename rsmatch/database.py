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


import math
import json
import datetime
import collections


class RSDatabase(object):
    """This class is a data structure for all of the assignment data.
    It is designed to be dumped to and loaded from a single file.
    """

    def __init__(self):
        self.path = None
        self.schools = []
        self.coaches = []
        self.catalog = Catalog()
        self.metadata = Metadata()
        self._assignments = []

    @property
    def assignments(self):
        return self._assignments.copy()

    @classmethod
    def from_path(cls, path):
        database = cls()
        database.path = path
        with open(path, 'r') as json_file:
            json_obj = json.load(json_file)
        schools = [School.from_json_obj(x) for x in json_obj['schools']]
        database.schools = schools
        coaches = [Coach.from_json_obj(x) for x in json_obj['coaches']]
        database.coaches = coaches
        database.catalog = Catalog.from_json_obj(json_obj['catalog'])
        database.metadata = Metadata.from_json_obj(json_obj['metadata'])
        database.init_catalog()
        for x in json_obj['assignments']:
            assign = tuple(x['assign'])
            manual = bool(x['manual'])
            timestamp = x['timestamp']
            if not manual:
                database.check_assignment(assign)
            database.add_assignment(assign, manual=manual, timestamp=timestamp)
        return database

    def save(self, path=None):
        if path is None:
            path = self.path
        if path is None:
            raise ValueError('No path specified')
        json_obj = collections.OrderedDict([
            ('metadata', self.metadata.to_json_obj()),
            ('assignments', self._assignments),
            ('schools', [x.to_json_obj() for x in self.schools]),
            ('coaches', [x.to_json_obj() for x in self.coaches]),
            ('catalog', self.catalog.to_json_obj())])
        with open(path, 'w') as json_file:
            json.dump(json_obj, json_file, indent=2)
        self.path = path

    def init_catalog(self):
        self.catalog.reset()
        for school in self.schools:
            for student in school.students:
                self.catalog.assign_guid(student)
            for teacher in school.teachers:
                self.catalog.assign_guid(teacher)
        for coach in self.coaches:
            coach.guid = self.catalog.assign_guid(coach)

    def find_school(self, teacher_or_student):
        for school in self.schools:
            for teacher in school.teachers:
                if teacher_or_student == teacher:
                    return school
            for student in school.teachers:
                if teacher_or_student == student:
                    return school
        return None

    def add_assignment(self, assign, manual=False, timestamp=None):
        day, slot, _, s_guid, c_guid = assign
        student = self.catalog.get_obj(s_guid)
        coach = self.catalog.get_obj(c_guid)
        
        student.assigned = True
        coach.assigned_days.add(day)
        coach.assignments.add(assign)
        for slot_i in range(self.metadata.slots_per_assignment):
            coach.schedule[day][slot + slot_i] = 2
            student.schedule[day][slot + slot_i] = 2
            
        index = 0
        for assign_i in range(len(self._assignments)):
            curr_assign = self._assignments[assign_i]['assign']
            if curr_assign < assign:
                index = assign_i + 1
            elif curr_assign == assign:
                return
            elif curr_assign > assign:
                break
        self._assignments.insert(index, {
            'assign': assign,
            'manual': manual,
            'timestamp': timestamp,
        })
        
    def check_assignment(self, assign):
        day, slot, t_guid, s_guid, c_guid = assign
        teacher = self.catalog.get_obj(t_guid)
        student = self.catalog.get_obj(s_guid)
        coach = self.catalog.get_obj(c_guid)
        school = self.find_school(teacher)
        day_str = self.metadata.day_to_str(day)
        time_str = self.metadata.slot_to_time(slot)
        num_slots = self.metadata.slots_per_assignment
        for slot_val in coach.schedule[day][slot:slot + num_slots]:
            if not slot_val:
                raise ValueError(
                    'Coach not available %s at %s' % (day_str, time_str))
        for slot_val in student.schedule[day][slot:slot + num_slots]:
            if not slot_val:
                raise ValueError(
                    'Student not available %s at %s' % (day_str, time_str))
        for curr in self._assignments:
            curr_assign = curr['assign']
            curr_day, curr_slot, _, curr_s, curr_c = curr_assign
            curr_school = self.find_school(teacher)
            if curr_assign == assign:
                raise ValueError('Duplicate assignment')
            if curr_s == s_guid:
                raise ValueError('Student already assigned %s %s %s' % (student.to_json_obj(), assign, curr_assign))
            if (curr_day, curr_slot, curr_c) == (day, slot, c_guid):
                raise ValueError(
                    'Coach already assigned on %s at %s' %
                    (day_str, time_str))
            if (curr_day, curr_c) == (day, c_guid) and curr_school != school:
                raise ValueError(
                    'Coach already assigned to a different school on %s' %
                    day_str)


class Metadata(object):

    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

    def __init__(self):
        self.minutes_per_slot = 15
        self.minutes_per_assignment = 30
        self.start_time = datetime.timedelta(hours=8, minutes=30)
        self.end_time = datetime.timedelta(hours=15, minutes=30)
        self.slots_per_assignment = int(
            math.ceil(self.minutes_per_assignment / self.minutes_per_slot))

    def time_to_slot(self, time_str):
        hours, minutes = time_str.split(':')
        curr_time = datetime.timedelta(hours=int(hours), minutes=int(minutes))
        if curr_time < self.start_time:
            curr_time = curr_time + datetime.timedelta(hours=12)
        if curr_time > self.end_time:
            raise ValueError(
                'Time falls outside window %s' % curr_time)
        delta_m = (curr_time - self.start_time).total_seconds() // 60
        return int(delta_m // self.minutes_per_slot)

    def slot_to_time(self, slot):
        delta = datetime.timedelta(minutes=self.minutes_per_slot * slot)
        slot_time = self.start_time + delta
        seconds = slot_time.total_seconds()
        hours = int(seconds // (60 * 60))
        seconds -= hours * (60 * 60)
        minutes = int(seconds // 60)
        #am_pm = 'AM'
        if hours > 12:
            hours -= 12
            #am_pm = 'PM'
        return '%d:%02d' % (hours, minutes)
    
    def day_to_str(self, day):
        return self.DAYS[day]

    def str_to_day(self, day_str):
        return self.DAYS.index(day_str)

    @property
    def num_slots(self):
        total_m = (self.end_time - self.start_time).total_seconds() // 60
        return int(total_m // self.minutes_per_slot)

    @property
    def num_days(self):
        return 5

    def to_json_obj(self):
        times = []
        for time_dt in (self.start_time, self.end_time):
            seconds = time_dt.total_seconds()
            hours = int(seconds // (60 * 60))
            seconds -= hours * (60 * 60)
            minutes = int(seconds // 60)
            times.append('%02d:%02d' % (hours, minutes))
        return collections.OrderedDict([
            ('minutes_per_slot', self.minutes_per_slot),
            ('minutes_per_assignment', self.minutes_per_assignment),
            ('start_time', times[0]),
            ('end_time', times[1])])
    
    @classmethod
    def from_json_obj(cls, json_obj):
        metadata = cls()
        metadata.minutes_per_slot = int(json_obj['minutes_per_slot'])
        metadata.minutes_per_assignment = int(
            json_obj['minutes_per_assignment'])
        times = []
        for time_str in (json_obj['start_time'], json_obj['end_time']):
            hours, mins = time_str.split(':')
            times.append(datetime.timedelta(
                hours=int(hours), minutes=int(mins)))
        metadata.start_time = times[0]
        metadata.end_time = times[1]
        metadata.slots_per_assignment = int(math.ceil(
            metadata.minutes_per_assignment / metadata.minutes_per_slot))
        return metadata


class Catalog(object):
    
    def __init__(self):
        self.obj_to_guid = {}
        self.guid_to_obj = {}
        self.curr_student = 100000
        self.curr_coach = 200000
        self.curr_teacher = 300000

    def reset(self):
        self.obj_to_guid = {}
        self.guid_to_obj = {}

    def assign_guid(self, obj):
        obj_guid = obj.guid
        if obj_guid is None:
            if obj in self.obj_to_guid:
                obj_guid = self.obj_to_guid[obj]
            elif isinstance(obj, Student):
                obj_guid = self.curr_student
                self.curr_student += 1
            elif isinstance(obj, Coach):
                obj_guid = self.curr_coach
                self.curr_coach += 1
            elif isinstance(obj, Teacher):
                obj_guid = self.curr_teacher
                self.curr_teacher += 1
        obj.guid = obj_guid
        self.obj_to_guid[obj] = obj_guid
        self.guid_to_obj[obj_guid] = obj
        return obj_guid

    def get_guid(self, obj):
        return self.obj_to_guid[obj]

    def get_obj(self, obj_guid):
        return self.guid_to_obj[obj_guid]

    def to_json_obj(self):
        return collections.OrderedDict([
            ('curr_student', self.curr_student),
            ('curr_coach', self.curr_coach),
            ('curr_teacher', self.curr_teacher)])

    @classmethod
    def from_json_obj(cls, json_obj):
        catalog = cls()
        catalog.curr_student = json_obj['curr_student']
        catalog.curr_coach = json_obj['curr_coach']
        catalog.curr_other = json_obj['curr_teacher']
        return catalog


class School(object):

    def __init__(self):
        self.name = None
        self.students = []
        self.teachers = []

    def to_json_obj(self):
        return collections.OrderedDict([
            ('name', self.name),
            ('students', [x.to_json_obj() for x in self.students]),
            ('teachers', [x.to_json_obj() for x in self.teachers])])

    @classmethod
    def from_json_obj(cls, json_obj):
        school = cls()
        school.name = json_obj['name']

        json_students = json_obj['students']
        students = [Student.from_json_obj(x) for x in json_students]
        school.students = students

        json_teachers = json_obj['teachers']
        teachers = [Teacher.from_json_obj(x) for x in json_teachers]
        school.teachers = teachers
        return school


class Teacher(object):

    def __init__(self):
        self.guid = None
        self.email = None
        self.first = None
        self.last = None
        self.grade = None

    def to_json_obj(self):
        return collections.OrderedDict([
            ('guid', self.guid),
            ('email', self.email),
            ('first', self.first),
            ('last', self.last),
            ('grade', self.grade)])

    @classmethod
    def from_json_obj(cls, json_obj):
        teacher = cls()
        teacher.guid = json_obj['guid']
        teacher.email = json_obj['email']
        teacher.first = json_obj['first']
        teacher.last = json_obj['last']
        teacher.grade = json_obj['grade']
        return teacher


class Student(object):

    def __init__(self):
        self.guid = None
        self.student_id = None
        self.teacher = None
        self.first = None
        self.last = None
        self.grade = None
        self.gender = None
        self.ell = None
        self.schedule = None
        self.assigned = False

    def to_json_obj(self):
        return collections.OrderedDict([
            ('guid', self.guid),
            ('student_id', self.student_id),
            ('teacher', self.teacher),
            ('first', self.first),
            ('last', self.last),
            ('grade', self.grade),
            ('gender', self.gender),
            ('ell', self.ell),
            ('schedule', self.schedule)])

    @classmethod
    def from_json_obj(cls, json_obj):
        student = cls()
        student.guid = json_obj['guid']
        student.student_id = json_obj['student_id']
        student.teacher = json_obj['teacher']
        student.first = json_obj['first']
        student.last = json_obj['last']
        student.grade = json_obj['grade']
        student.gender = json_obj['gender']
        student.ell = json_obj['ell']
        student.schedule = json_obj['schedule']
        return student


class Coach(object):

    def __init__(self):
        self.guid = None
        self.vid = None
        self.first = None
        self.last = None
        self.schools = None
        self.grades = None
        self.num_students = None
        self.num_days = None
        self.schedule = None
        self.assigned_days = set()
        self.assignments = set()

    def to_json_obj(self):
        return collections.OrderedDict([
            ('guid', self.guid),
            ('vid', self.vid),
            ('email', self.email),
            ('first', self.first),
            ('last', self.last),
            ('schools', self.schools),
            ('grades', self.grades),
            ('num_days', self.num_days),
            ('num_students', self.num_students),
            ('schedule', self.schedule)])

    @classmethod
    def from_json_obj(cls, json_obj):
        coach = cls()
        coach.guid = json_obj['guid']
        coach.vid = json_obj['vid']
        coach.email = json_obj['email']
        coach.first = json_obj['first']
        coach.last = json_obj['last']
        coach.schools = json_obj['schools']
        coach.grades = json_obj['grades']
        coach.num_students = json_obj['num_students']
        coach.num_days = json_obj['num_days']
        coach.schedule = json_obj['schedule']
        return coach