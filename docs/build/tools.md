# Tools — the capability catalog

Every capability is a Python function decorated with `@tool({...})` (an OpenAI function
schema). The brain picks and calls them. **42 tools** currently, by category:

## Time / weather / location
| Tool | Does |
|---|---|
| `get_time` | current date/time/day |
| `get_weather(city?)` | weather; **no city → uses dynamic location** (GPS→saved→IP) |
| `get_location` | current location (GPS via CoreLocationCLI → saved → IP) |
| `search_nearby(query)` | places near the user — Google Maps centred on real GPS coords, in Chrome |
| `get_distance(destination)` | distance + driving time, answered by voice. Google Maps geocoding (nearest-first 17z→13z, headless) → OSRM routing; always states the matched place name |

## Device awareness (read state)
| Tool | Does |
|---|---|
| `get_battery` | battery % + charging |
| `get_active_app` | foreground app |
| `get_open_apps` | visible apps |
| `get_now_playing` | Spotify/Music current track |
| `read_clipboard` | clipboard text |

## Mac control (actions)
| Tool | Does |
|---|---|
| `control_volume(level)` | set output volume 0–100 |
| `open_app(name)` | fuzzy-match installed apps and open (e.g. "youtube" → "BYouTube") |
| `list_apps` | list installed apps |
| `open_website(site)` | open a site in **real Chrome, foreground** (youtube, gmail, url…) |
| `open_location(place?)` | open a place in Google Maps |
| `quit_app(name)` | quit an app |
| `media_control(action)` | play/pause/next/previous |
| `set_clipboard(text)` | copy text to clipboard |

## Screen vision
| Tool | Does |
|---|---|
| `see_screen(question)` | screenshot → local vision model (Ollama `qwen2.5vl:3b`) → answer. Screenshot is **deleted after** (privacy). Slow first call on 8 GB (~155s to load model). |

## Web + email
| Tool | Does |
|---|---|
| `web_search(query)` | search (DuckDuckGo via headed Chromium) |
| `read_page(url)` | fetch a page's text |
| `compare_prices(product)` | price comparison via Google Shopping + opens it in Chrome (extraction is best-effort; see ISSUES) |
| `open_gmail(account?)` | open Gmail (account index) |
| `compose_email(to, subject, body, account?)` | open a **pre-filled draft** — user presses Send (ban-safe) |

## Admin / coding — **GATED** (asks to confirm)
| Tool | Does |
|---|---|
| `install_app(name)` | Homebrew install. **Gated.** |
| `run_command(command)` | run a shell command in the workspace (run/debug code). **Gated.** |
| `write_file(filename, content)` | write code/text to `data/workspace/` (sandboxed) |

## Stocks (read-only, no key)
| Tool | Does |
|---|---|
| `get_stock(symbol)` | price + day change via Yahoo's public chart API. No trading, ever. |
| `job_status` | job-copilot status: role count + top matches (needs its FastAPI running) |

## Apple Reminders & Notes (iCloud-synced with the iPhone)
| Tool | Does |
|---|---|
| `add_reminder(text, hours_from_now?)` | add a reminder (fires on the phone too) |
| `list_reminders` | open reminders |
| `create_note(title, body)` | new Apple Note |
| `search_notes(query)` | find notes by title/content |

## Projects & coding
| Tool | Does |
|---|---|
| `list_projects` / `project_info` | Jarvis's knowledge of all the user's laptop projects |
| `delegate_coding(project, task)` | **gated** — hands a coding task to the Claude Code CLI on that project |
| `get_distance(destination)` | see Time/location |

## Memory
| Tool | Does |
|---|---|
| `remember_fact(fact, topic?)` | store a durable fact; recalled via context injection |

## Voice control (self)
| Tool | Does |
|---|---|
| `set_voice`, `rename_self`, `set_emotion`, `set_pitch`, `set_rate` | change Jarvis's own voice/identity/delivery |

## Adding a tool

```python
# src/tools/mytool.py
from brain import tool  # and: gate  — if it should require confirmation

@tool({"name": "do_thing",
       "description": "what it does (the brain reads this to decide when to call it)",
       "parameters": {"type": "object",
           "properties": {"x": {"type": "string"}}, "required": ["x"]}})
def do_thing(x: str):
    return {"result": ...}          # return structured data, never a guessed value

# gate("do_thing")                  # optional: require user confirmation
```
Then add `import tools.mytool` in `listen.py`. Update the capabilities sentence in
`brain.run_turn` if it's a headline ability. Done — the brain can now call it.
