2025-05-21T14:00:35.817848966Z ==> Cloning from https://github.com/Dionexu/cryptoday
2025-05-21T14:00:36.240377057Z ==> Checking out commit 3173d0af649d83d456a521fa39aabb31bbdb4d5e in branch main
2025-05-21T14:00:43.17087797Z ==> Using Python version 3.11.11 (default)
2025-05-21T14:00:43.200637128Z ==> Docs on specifying a Python version: https://render.com/docs/python-version
2025-05-21T14:00:47.038584695Z ==> Using Poetry version 1.7.1 (default)
2025-05-21T14:00:47.093581757Z ==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
2025-05-21T14:00:47.097911565Z ==> Running build command 'pip install -r requirements.txt'...
2025-05-21T14:00:47.760745791Z Collecting aiogram==3.2.0 (from -r requirements.txt (line 1))
2025-05-21T14:00:47.825936324Z   Downloading aiogram-3.2.0-py3-none-any.whl.metadata (7.2 kB)
2025-05-21T14:00:48.71088579Z Collecting aiohttp==3.9.3 (from -r requirements.txt (line 2))
2025-05-21T14:00:48.723693438Z   Downloading aiohttp-3.9.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (7.4 kB)
2025-05-21T14:00:48.880578234Z Collecting pytz (from -r requirements.txt (line 3))
2025-05-21T14:00:48.893077093Z   Downloading pytz-2025.2-py2.py3-none-any.whl.metadata (22 kB)
2025-05-21T14:00:49.0849342Z Collecting python-dotenv (from -r requirements.txt (line 4))
2025-05-21T14:00:49.097426488Z   Downloading python_dotenv-1.1.0-py3-none-any.whl.metadata (24 kB)
2025-05-21T14:00:49.343135614Z Collecting aiofiles~=23.2.1 (from aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:49.355406846Z   Downloading aiofiles-23.2.1-py3-none-any.whl.metadata (9.7 kB)
2025-05-21T14:00:49.597698701Z Collecting certifi>=2023.7.22 (from aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:49.60985782Z   Downloading certifi-2025.4.26-py3-none-any.whl.metadata (2.5 kB)
2025-05-21T14:00:49.857843672Z Collecting magic-filter<1.1,>=1.0.12 (from aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:49.871713781Z   Downloading magic_filter-1.0.12-py3-none-any.whl.metadata (1.5 kB)
2025-05-21T14:00:50.160827987Z Collecting pydantic<2.6,>=2.4.1 (from aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:50.173342696Z   Downloading pydantic-2.5.3-py3-none-any.whl.metadata (65 kB)
2025-05-21T14:00:50.192969055Z      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 65.6/65.6 kB 4.0 MB/s eta 0:00:00
2025-05-21T14:00:50.24401021Z Collecting typing-extensions<=5.0,>=4.7.0 (from aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:50.257289192Z   Downloading typing_extensions-4.13.2-py3-none-any.whl.metadata (3.0 kB)
2025-05-21T14:00:50.306193384Z Collecting aiosignal>=1.1.2 (from aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:50.31895361Z   Downloading aiosignal-1.3.2-py2.py3-none-any.whl.metadata (3.8 kB)
2025-05-21T14:00:50.373472928Z Collecting attrs>=17.3.0 (from aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:50.387562113Z   Downloading attrs-25.3.0-py3-none-any.whl.metadata (10 kB)
2025-05-21T14:00:50.48002727Z Collecting frozenlist>=1.1.1 (from aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:50.496115974Z   Downloading frozenlist-1.6.0-cp311-cp311-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (16 kB)
2025-05-21T14:00:50.829245618Z Collecting multidict<7.0,>=4.5 (from aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:50.842125628Z   Downloading multidict-6.4.4-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (5.3 kB)
2025-05-21T14:00:51.164033451Z Collecting yarl<2.0,>=1.0 (from aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:51.194065696Z   Downloading yarl-1.20.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (72 kB)
2025-05-21T14:00:51.218304791Z      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 72.4/72.4 kB 2.8 MB/s eta 0:00:00
2025-05-21T14:00:51.380639548Z Collecting annotated-types>=0.4.0 (from pydantic<2.6,>=2.4.1->aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:51.393543319Z   Downloading annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
2025-05-21T14:00:52.265079269Z Collecting pydantic-core==2.14.6 (from pydantic<2.6,>=2.4.1->aiogram==3.2.0->-r requirements.txt (line 1))
2025-05-21T14:00:52.279456733Z   Downloading pydantic_core-2.14.6-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.5 kB)
2025-05-21T14:00:52.339912156Z Collecting idna>=2.0 (from yarl<2.0,>=1.0->aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:52.352457606Z   Downloading idna-3.10-py3-none-any.whl.metadata (10 kB)
2025-05-21T14:00:52.423531902Z Collecting propcache>=0.2.1 (from yarl<2.0,>=1.0->aiohttp==3.9.3->-r requirements.txt (line 2))
2025-05-21T14:00:52.43601303Z   Downloading propcache-0.3.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (10 kB)
2025-05-21T14:00:52.472203817Z Downloading aiogram-3.2.0-py3-none-any.whl (470 kB)
2025-05-21T14:00:52.504636234Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 470.1/470.1 kB 15.6 MB/s eta 0:00:00
2025-05-21T14:00:52.520603334Z Downloading aiohttp-3.9.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (1.3 MB)
2025-05-21T14:00:52.545696214Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.3/1.3 MB 58.2 MB/s eta 0:00:00
2025-05-21T14:00:52.558338837Z Downloading pytz-2025.2-py2.py3-none-any.whl (509 kB)
2025-05-21T14:00:52.570346531Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 509.2/509.2 kB 52.4 MB/s eta 0:00:00
2025-05-21T14:00:52.583121428Z Downloading python_dotenv-1.1.0-py3-none-any.whl (20 kB)
2025-05-21T14:00:52.603245342Z Downloading aiofiles-23.2.1-py3-none-any.whl (15 kB)
2025-05-21T14:00:52.62320848Z Downloading aiosignal-1.3.2-py2.py3-none-any.whl (7.6 kB)
2025-05-21T14:00:52.658190802Z Downloading attrs-25.3.0-py3-none-any.whl (63 kB)
2025-05-21T14:00:52.707090124Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 63.8/63.8 kB 1.1 MB/s eta 0:00:00
2025-05-21T14:00:52.720075047Z Downloading certifi-2025.4.26-py3-none-any.whl (159 kB)
2025-05-21T14:00:52.775092749Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 159.6/159.6 kB 2.8 MB/s eta 0:00:00
2025-05-21T14:00:52.787877036Z Downloading frozenlist-1.6.0-cp311-cp311-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl (313 kB)
2025-05-21T14:00:52.830224715Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 313.6/313.6 kB 9.1 MB/s eta 0:00:00
2025-05-21T14:00:52.84260454Z Downloading magic_filter-1.0.12-py3-none-any.whl (11 kB)
2025-05-21T14:00:52.902938959Z Downloading multidict-6.4.4-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (223 kB)
2025-05-21T14:00:52.933266154Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 223.7/223.7 kB 7.7 MB/s eta 0:00:00
2025-05-21T14:00:52.953701266Z Downloading pydantic-2.5.3-py3-none-any.whl (381 kB)
2025-05-21T14:00:53.099782144Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 381.9/381.9 kB 2.6 MB/s eta 0:00:00
2025-05-21T14:00:53.113490768Z Downloading pydantic_core-2.14.6-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
2025-05-21T14:00:53.192265561Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 26.9 MB/s eta 0:00:00
2025-05-21T14:00:53.205681357Z Downloading typing_extensions-4.13.2-py3-none-any.whl (45 kB)
2025-05-21T14:00:53.248086017Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 45.8/45.8 kB 890.5 kB/s eta 0:00:00
2025-05-21T14:00:53.263068559Z Downloading yarl-1.20.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (358 kB)
2025-05-21T14:00:53.274366522Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 358.1/358.1 kB 39.7 MB/s eta 0:00:00
2025-05-21T14:00:53.287392856Z Downloading annotated_types-0.7.0-py3-none-any.whl (13 kB)
2025-05-21T14:00:53.306572082Z Downloading idna-3.10-py3-none-any.whl (70 kB)
2025-05-21T14:00:53.315830245Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 70.4/70.4 kB 8.7 MB/s eta 0:00:00
2025-05-21T14:00:53.329349923Z Downloading propcache-0.3.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (232 kB)
2025-05-21T14:00:53.340520203Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 232.5/232.5 kB 24.4 MB/s eta 0:00:00
2025-05-21T14:00:53.498674077Z Installing collected packages: pytz, typing-extensions, python-dotenv, propcache, multidict, magic-filter, idna, frozenlist, certifi, attrs, annotated-types, aiofiles, yarl, pydantic-core, aiosignal, pydantic, aiohttp, aiogram
2025-05-21T14:00:54.760777395Z Successfully installed aiofiles-23.2.1 aiogram-3.2.0 aiohttp-3.9.3 aiosignal-1.3.2 annotated-types-0.7.0 attrs-25.3.0 certifi-2025.4.26 frozenlist-1.6.0 idna-3.10 magic-filter-1.0.12 multidict-6.4.4 propcache-0.3.1 pydantic-2.5.3 pydantic-core-2.14.6 python-dotenv-1.1.0 pytz-2025.2 typing-extensions-4.13.2 yarl-1.20.0
2025-05-21T14:00:54.935642161Z 
2025-05-21T14:00:54.935668492Z [notice] A new release of pip is available: 24.0 -> 25.1.1
2025-05-21T14:00:54.935673532Z [notice] To update, run: pip install --upgrade pip
2025-05-21T14:01:00.858902481Z ==> Uploading build...
2025-05-21T14:01:06.987504817Z ==> Uploaded in 5.0s. Compression took 1.1s
2025-05-21T14:01:07.009832495Z ==> Build successful 🎉
2025-05-21T14:01:09.401406289Z ==> Deploying...
2025-05-21T14:01:33.510237441Z ==> Running 'python main.py'
2025-05-21T14:01:47.594998381Z INFO:aiogram.dispatcher:Start polling
2025-05-21T14:01:47.755422909Z INFO:aiogram.dispatcher:Run polling for bot @dionexbot id=8006649444 - 'Dionex'
2025-05-21T14:01:49.109087927Z ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2025-05-21T14:01:49.109124238Z WARNING:aiogram.dispatcher:Sleep for 1.000000 seconds and try again... (tryings = 0, bot id = 8006649444)
2025-05-21T14:01:58.507358603Z ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2025-05-21T14:01:58.507380834Z WARNING:aiogram.dispatcher:Sleep for 1.072542 seconds and try again... (tryings = 1, bot id = 8006649444)
2025-05-21T14:02:07.716973088Z ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2025-05-21T14:02:07.717007109Z WARNING:aiogram.dispatcher:Sleep for 1.417389 seconds and try again... (tryings = 2, bot id = 8006649444)
2025-05-21T14:02:14.354129647Z ==> No open ports detected, continuing to scan...
2025-05-21T14:02:14.4469475Z ==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
2025-05-21T14:02:17.423589048Z ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2025-05-21T14:02:17.423617169Z WARNING:aiogram.dispatcher:Sleep for 1.697981 seconds and try again... (tryings = 3, bot id = 8006649444)
2025-05-21T14:02:27.448260452Z ERROR:aiogram.dispatcher:Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2025-05-21T14:02:27.448289943Z WARNING:aiogram.dispatcher:Sleep for 2.171946 seconds and try again... (tryings = 4, bot id = 8006649444)
