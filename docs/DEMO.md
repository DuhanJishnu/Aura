# Two-minute demo script

Setup: `python -m data.seed`, set `GEMINI_API_KEY`, `uvicorn app.main:app`, open http://localhost:8000 in Chrome or Edge
(for voice). Record the browser window with any screen recorder. Use a fresh tab so the saved size is empty.

| Time | Do | Say / point out |
|---|---|---|
| 0:00 | Type `hi`, `sports shoes`, `for me`, `9` | One question at a time. The grid appears before the sentence finishes. |
| 0:25 | `what do you think of the second one?` | An honest opinion with a trade-off, built only from catalog data. |
| 0:40 | `that's too expensive` | Cheaper alternatives in the same size, or an honest "nothing cheaper". |
| 0:55 | `compare the first and third` | Side-by-side table plus plain trade-offs. |
| 1:10 | `will it fit? I'm unsure about my size` | It admits it has no fit data and lists the sizes in stock. |
| 1:20 | Click Mic and say "I'll take the first one" | Voice in; then toggle "Speak replies" for voice out. |
| 1:30 | `place order` | Mock order confirmation; shoe size saved for next time. |
| 1:40 | Click **Clothes**, answer `casual`, `for me`, `M` | Same engine, letter sizes, no shoe size applied. |
| 1:50 | `I have a warm undertone`, then `sports shoes, size 9` | The reply says why some colors moved up ("tend to complement"). |
| 2:00 | `no thanks`, then `just browsing` | Backs off, shows nothing, asks nothing. Finish with `forget my profile`. |

Tips: say what the system is doing, not just what it shows ("the validator checked that price against the database"). Show
the `policy` field in the browser network tab once to make the rule table visible.
