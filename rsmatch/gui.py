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
import threading
from subprocess import Popen
import tkinter as tk
from tkinter import filedialog

from . import input
from . import output
from . import matcher
from . import database


def ask_for_file(string_var):
    initial_dir = None
    if string_var.get():
        initial_dir = os.path.dirname(string_var.get())
    string_var.set(
        filedialog.askopenfilename(
            title="Select file",
            filetypes=(('CSV files', '*.csv'), ('all files','*.*')),
            initialdir=initial_dir))

def ask_for_dir(string_var):
    initial_dir = None
    if string_var.get():
        initial_dir = string_var.get()
    string_var.set(
        filedialog.askdirectory(
            title="Select Directory",
            mustexist=True,
            initialdir=initial_dir))

class MatcherGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.referrals_path = tk.StringVar()
        self.coaches_path = tk.StringVar()
        self.assignments_path = tk.StringVar()
        self.output_dir_path = tk.StringVar()
        self.first_choice = tk.IntVar()
        self.first_choice.set(True)
        self.second_choice = tk.IntVar()
        self.greatest_need = tk.IntVar()
        self.database_path = None
        self.btn_database = None
        self.btn_report = None
        self.lst_school = None
        self.lst_school_data = []
        self.btn_start = None

        self.title('RS Matcher')

        tk.Label(
            self,
            text='STEP 1: Select teacher referral CSV file input').pack(
                anchor=tk.W)

        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        self.referral_entry = tk.Entry(
            frame, width=50, textvariable=self.referrals_path)
        self.referral_entry.grid(
            row=0, column=0, columnspan=4, padx=2, pady=2, sticky=tk.W)
        tk.Button(
            frame,
            text='Browse',
            command=lambda: ask_for_file(self.referrals_path)).grid(
                row=0, column=4, padx=2, pady=2, sticky=tk.W)

        tk.Label(
            self,
            text='STEP 2: Select coach registration CSV file input').pack(
                anchor=tk.W)

        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        self.referral_entry = tk.Entry(
            frame, width=50, textvariable=self.coaches_path)
        self.referral_entry.grid(
            row=0, column=0, columnspan=4, padx=2, pady=2, sticky=tk.W)
        tk.Button(
            frame,
            text='Browse',
            command=lambda: ask_for_file(self.coaches_path)).grid(
                row=0, column=4, padx=2, pady=2, sticky=tk.W)

        tk.Label(
            self,
            text='STEP 3 (optional): Select assignments CSV file input').pack(
                anchor=tk.W)

        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        self.referral_entry = tk.Entry(
            frame, width=50, textvariable=self.assignments_path)
        self.referral_entry.grid(
            row=0, column=0, columnspan=4, padx=2, pady=2, sticky=tk.W)
        tk.Button(
            frame,
            text='Browse',
            command=lambda: ask_for_file(self.assignments_path)).grid(
                row=0, column=4, padx=2, pady=2, sticky=tk.W)

        tk.Label(
            self,
            text='STEP 4: Select folder for saving output').pack(
                anchor=tk.W)

        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        self.referral_entry = tk.Entry(
            frame, width=50, textvariable=self.output_dir_path)
        self.referral_entry.grid(
            row=0, column=0, columnspan=4, padx=2, pady=2, sticky=tk.W)
        tk.Button(
            frame,
            text='Browse',
            command=lambda: ask_for_dir(self.output_dir_path)).grid(
                row=0, column=4, padx=2, pady=2, sticky=tk.W)
                
        tk.Label(self, text='STEP 5: Create database from input files').pack(
            anchor=tk.W, padx=2, pady=2)
        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        self.btn_database = tk.Button(
            frame,
            text='Create Database',
            command=self.create_database)
        self.btn_database.grid(row=0, column=0, padx=2, pady=2)
        self.btn_report = tk.Button(
            frame,
            text='Create Report',
            state=tk.DISABLED,
            command=self.create_report)
        self.btn_report.grid(row=0, column=1, padx=2, pady=2)
        
        tk.Label(self, text='STEP 6: Select a school for matching').pack(anchor=tk.W)
        self.lst_school = tk.Listbox(self, selectmode=tk.SINGLE)
        self.lst_school.pack(anchor=tk.W, padx=2, pady=2)

        tk.Label(self, text='STEP 7: Select school preferences to use').pack(anchor=tk.W)
        frame = tk.Frame()
        frame.pack(anchor=tk.W)
        tk.Checkbutton(frame, text='First', variable=self.first_choice).grid(
            row=0, column=0, columnspan=1, padx=2, pady=2, sticky=tk.W)
        tk.Checkbutton(frame, text='Second', variable=self.second_choice).grid(
            row=0, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W)
        tk.Checkbutton(frame, text='Greatest Need', variable=self.greatest_need).grid(
            row=0, column=2, columnspan=1, padx=2, pady=2, sticky=tk.W)

        tk.Label(self, text='STEP 8: Start matching algorithm').pack(anchor=tk.W)
        self.btn_start = tk.Button(
            self,
            text='Start',
            state=tk.DISABLED,
            command=self.run)
        self.btn_start.pack(anchor=tk.W, padx=2, pady=2)

    def create_database(self):
        referrals_path = self.referrals_path.get()
        coaches_path = self.coaches_path.get()
        assignments_path = self.assignments_path.get()
        output_dir_path = self.output_dir_path.get()
        output_path = os.path.join(output_dir_path, 'rsdb.json')
        self.database_path = None
        input.create_database(
            referrals_path, coaches_path, assignments_path, output_path)
        self.database_path = output_path
        self.btn_database.config(state=tk.DISABLED)
        
        rsdb = database.RSDatabase.from_path(output_path)
        
        self.lst_school.delete(0, tk.END)
        self.lst_school_data = []
        for school in sorted(rsdb.schools, key=lambda x: x.name):
            self.lst_school.insert(tk.END, school.name)
            self.lst_school_data.append(school.name)
        self.lst_school.config(state=tk.NORMAL)
        if self.lst_school_data:
            self.lst_school.select_set(0)
        self.btn_report.config(state=tk.NORMAL)
        self.btn_start.config(state=tk.NORMAL)

    def create_report(self):
        self.btn_report.config(state=tk.DISABLED)
        output_dir_path = self.output_dir_path.get()
        rsdb = database.RSDatabase.from_path(self.database_path)
        out = output.MatcherOutput(rsdb, dir=output_dir_path)
        output_path = os.path.join(output_dir_path, 'report.txt')
        out.create_report(output_path)
        self.btn_report.config(state=tk.NORMAL)
        Popen(['notepad.exe', output_path])
        
    def run(self):
        self.btn_start.config(state=tk.DISABLED)
        def runner():
            try:
                school_name = self.lst_school_data[
                    self.lst_school.curselection()[0]]
                matcher.do_match(
                    self.database_path,
                    school=school_name,
                    first=self.first_choice.get(),
                    second=self.second_choice.get(),
                    greatest=self.greatest_need.get())
                output_dir_path = self.output_dir_path.get()
                rsdb = database.RSDatabase.from_path(self.database_path)
                db_output = output.MatcherOutput(rsdb, dir=output_dir_path)
                db_output.create_assignments_csv()
            except Exception as ex:
                print('ERROR: %s' % ex)
            self.btn_start.config(state=tk.NORMAL)
        run_thread = threading.Thread(target=runner)
        run_thread.start()


def main():
    gui = MatcherGUI()
    gui.mainloop()


if __name__ == '__main__':
    main()