# RSMatcher

RSMatcher is a custom application written for a non-profit educational program that matches volunteer reading coaches with children in need of reading assistance.
The coaches meet and read with each student for 30 minutes each week.
There may be hundreds of coaches and over one thousand students.
RSMatcher is an implementation of an algorithm to find a near-optimal scheduling solution.
An optimal solution matches as many students as coaches are willing to take while also meeting the scheduling restrictions of the coaches and schools.
The problem space is first converted to a graph in which finding all cycles identifies possible schedule additions.
Heuristic sorting is used to prioritize more efficient additions (e.g. a coach meets with multiple students at the same school back-to-back).
At multiple points, shuffling and round-robin interleaving is used to remove bias.
Then a branch and bound traversal of the solution tree is used to converge on a near-optimal solution while also culling solutions with relatively poor scores.
