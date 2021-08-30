# RSMatcher

## Theory of Operation

The Reading Seed Matcher software is designed to take 3 inputs: student
referrals, coach registration, and existing assignments. All input files
are comma-separated value (CSV) format text files. The matching algorithm
is run on each school separately. After each run of the algorithm, a new
assignments CSV file is created in the output directory.

## How to Run the Software

To run the Reading Seed Matcher, double-click on the _RSMatcher.exe_
file. A command prompt window will open first, followed by a graphical user
interface window.

## CSV Files

### Referrals

The referrals CSV file is expected to have one or more lines per teacher, but
only one with schedule information. Each line can have multiple students from
the same teacher. It is assumed that each teacher has a unique and consistent
email address.

### Coach Registration

The coach registration CSV file is expected to have one line per coach. It is
assumed that each coach as a unique volunteer ID (VID).

### Assignments

The assignments input is also the primary output from the matching algorithm.
It is a CSV list of all student-coach assignments that have been made. When
running the Reading Seed Matcher, the assignments file can be specified. This
will instruct the algorithm to preserve those existing assignments, but it
will still try to make any new matches it can make with any new updates to
the input.

If an assignment has been manually created, but conflicts with schedules, it
will be excluded as an invalid assignment. To override this behavior, the
last column of the assignments CSV file contains either a timestamp or the
text "manual" to indicate that this assignment was manually created and does
not need to be checked for conflicts.

The assignments file is created in the output directory and it will
overwritten on each run of the algorithm for a single school.

## Database

Reading Seed Matcher creates a database each time it is run. Once all input
files and the output directory have been specified, clicking the
**Create Database** button will create the database file called _rsdb.json_
in the specified output directory. This file must not be deleted while the
software is running. However, it may be deleted after the software has been
closed. After the database has been created, the **Create Database** button
is disabled. To specify different input files, Reading Seed Matcher must be
closed and restarted.