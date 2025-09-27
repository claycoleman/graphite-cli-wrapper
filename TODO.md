[x] Add a way to filter out Graphite CLI version warnings from command output.
[x] If i have branch A and B on top of A, then A gets merged and I run `gt sync`, branch B is correctly restacked on top of trunk. however, running gt submit doesn't parse the stack comment properly and removes the previous stack from the PR. And our tests don't fail even though in practice the PR comment is not properly updated. I think it might be due to the fact that we changed the dividers between stack comments.
[x] add version checking to the wrapper. probably not every time, unless we can run in parallel and output at the end of the command...? idk how often we should do this. 
[x] error with gt submit 
Parsing the stack...

Stack to submit:
> rjha/updating_processing_window_time
  main

Submitting 1 branch in single mode...
Force-pushed branch: rjha/updating_processing_window_time

Updating stack references...
Using rjha/updating_processing_window_time as source of truth for historical context
Updating stack comment for PR: rjha/updating_processing_window_time
Error running command: gh pr comment rjha/updating_processing_window_time --body "### Stack

main
└ **fix: update batch API processing window from "24 hours" to "24 hours to 7 days" (#2804) ⬅️**"

accepts at most 1 arg(s), received 6
[x] gt sync just a single stack instead of all stacks
[x] gt sync -cs fails if the stack isn't currently at the top of the stack because the newline with (needs restack) blows up the stack pr parsing.
[x] if the gh repo has a PR template, the draft PR doesn't get filled with the template.
[ ] sometimes when running a command and typing, my termainl doesn't pick up the typed command after the current command is finished.
[ ] weird error when running gt on untracked branch: > gt sync -cs

📋 Parsing current stack from branch: cyestrau/batch-project-filtering...
Error running command: /Users/ccoleman/.local/share/fnm/node-versions/v20.18.0/installation/lib/node_modules/@claycoleman/gt-wrapper/bin/../node_modules/@withgraphite/graphite-cli/graphite.js ls --stack --reverse
ERROR: Cannot perform this operation on untracked branch cyestrau/batch-project-filtering.
You can track it by specifying its parent with gt track.
No error output

we should clean this up or just do some checks to see if the branch is tracked for gt sync and proabbly gt submit
[x] if unknown args are given to our overridden commands [sync, submit], we should exit. honesetly our parsing needs to imporve a lot for those two commands, but shouldn't get parsed if it's not those commands.
[ ] can't submit if there is a PR in the stack that needs restack .
[ ] Add better CLI support without preventing passing CLI args to the original Graphite CLI?