# Second annotator pack

Thank you for agreeing to help. About eight hours in total. Please spread it over
several sessions rather than one sitting.

## What this is for

We built a dataset of experimental details extracted from ninety-six machine
learning papers and their repositories. Every accuracy number in our paper is
measured against that dataset, and so far only one person has checked it, and
that person is also the author. A reviewer will find that.

Your job is to check a sample independently. We are not asking you to agree with
the existing answers. We are asking you to produce your own without seeing ours,
so we can measure how far apart two careful people end up. Disagreement is a
useful result, not a mistake.

## What is in here

```
CODEBOOK.md          the rules. Read this first.
SAMPLE.json          which studies were selected, and the seed used
01_study001/
  STUDY.md           title, paper link, PDF link, repository link
  annotate.csv       the rows you fill in
  additions.csv      anything real the rows missed
02_study002/
...
```

Twenty folders, one per study.

## How to do it

1. **Read `CODEBOOK.md`.** About ten minutes. It defines what counts as a
   dependency, when a version is specified, how to treat numbers copied from
   other papers. Most disagreement between annotators comes from definitions
   rather than carelessness, so this is the part that matters.

2. **Start with folders 01, 02 and 03 only.** Do those three, then stop and send
   them back. We will compare, find where the definitions were ambiguous, fix the
   codebook together, and only then will you do the remaining seventeen. Please
   do not do all twenty in one go. If a definition is unclear we would rather
   find out after three studies than after twenty.

3. **For each study**, open `STUDY.md`, read the paper and skim the repository,
   then work down `annotate.csv`. Put `K`, `D` or `U` in the `decision` column.
   Use `note` when something needs explaining, especially a `D` for a wrong value.

4. **Open the CSV in whatever you like**: Excel, Numbers, Google Sheets, a text
   editor. Keep the columns and the `item_id` values exactly as they are, and
   save back as CSV.

5. **Put anything the rows missed into `additions.csv`.**

6. **Send the folders back** after the first three, and again at the end.

## Three things that matter

**Work independently.** Please do not ask the author which answer is right, and
do not open any ground-truth file you come across in the repositories. The items
are deliberately mixed from several sources so you cannot tell which came from
where. That mixing is what makes the comparison meaningful.

**`U` is a real answer.** If you looked and cannot tell, mark `U`. A guess is
worse than an honest `U`.

**Do not revise earlier studies** after your understanding improves. Leave them
and mention it. Drift between early and late studies is something we want to see.

## Questions

Ask about the process at any time, and about anything in the codebook that is
unclear or self-contradictory. The only thing to avoid is asking what the answer
to a particular row should be.
