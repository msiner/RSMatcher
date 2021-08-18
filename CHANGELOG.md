# Changelog

This document contains high-level descriptions of the changes made to
the software in each released version.

## 2019/08/26 v4
- Detect invalid referral entries that select times for a day and NONE
- Write invalid input entries to output terminal
- Write invalid input entries to files in same directory as database

## 2019/09/16 v5
- Fix off-by-one error that was not picking up 2nd recess
- Extend default end time to 15:30 and fix bug in error path
- Add more useful error text for referrals without schedules and fix
  problem with referrals that use all possible student inputs
- Add manual assignments and assignment checks against schedules

## 2019/09/18 v6
- Change how pre-existing assignments are applied to the database and
  used in the matcher

## TBD v7
- Update to use 2021 CSV columns
- Last column of assignments CSV is now either a timestamp or "manual"
- Build script to release as single EXE file.