# ERP-CNC Adapter: Ред на инициализация

## 1. Цел

Този документ описва реда на стартиране на ERP-CNC Adapter, Eding CNC GUI и CNC Server при двата основни режима:

- автоматичен старт при Windows logon;
- ръчен старт чрез shortcut `START-CNC`.

Документът е техническо описание на последователността и задачите, които участват в стартирането.

## 2. Основни компоненти

### ERPCNCAdapter

Основната Windows Scheduled Task за стартиране на adapter приложението.

Тази задача стартира:

```text
scripts\launch_adapter_hidden.vbs
```

VBS launcher-ът стартира:

```text
erp-cnc-adapter.exe
```

Целта на VBS launcher-а е adapter-ът да се стартира без видим terminal прозорец.

### ERPCNCAdapterManualStart

Windows Scheduled Task за ръчен старт чрез `START-CNC`.

Тази задача стартира:

```text
scripts\run_start_cnc_hidden.vbs
```

VBS launcher-ът стартира:

```text
scripts\restart.bat
```

с environment marker:

```text
ERPCNC_MANUAL_TASK=1
```

Този marker показва на `restart.bat`, че вече се изпълнява през elevated/manual task и може да извърши реалната стартова последователност.

### ERPCNCAdapterEdingHandoff

Windows Scheduled Task/helper за стартиране на Eding GUI през правилния Windows потребителски session.

Тази задача стартира:

```text
scripts\start_eding_handoff.ps1
```

Използва се когато `auto_start_eding_gui` е включено. При manual `START-CNC` flow основната последователност стартира `start_eding_handoff.ps1` от `restart.bat`; scheduled task/helper-ът съществува за elevated/session handoff и fallback сценарии.

### ERPCNCAdapterWatchdog

Watchdog задача, която проверява adapter процеса периодично.

При нормален автоматичен режим може да рестартира adapter-а при проблем.

При manual-start режим watchdog auto-start се изключва, за да не стартира adapter-а самостоятелно.

## 3. Автоматичен старт при Windows logon

Този режим се използва когато настройката е включена:

```json
"auto_start_adapter_on_logon": true
```

и Scheduled Task `ERPCNCAdapter` е enabled.

## 4. Последователност при автоматичен старт

### 4.1 Windows logon

Първо потребителят влиза в Windows.

Ако adapter-ът е инсталиран да работи като Windows account, задачата е създадена с:

```text
LogonType: Interactive
RunLevel: Highest
```

### 4.2 Стартиране на ERPCNCAdapter

Windows Task Scheduler стартира задачата:

```text
ERPCNCAdapter
```

Задачата има startup delay. Стандартната стойност е:

```text
90 seconds
```

Това закъснение дава време на Windows, drivers и CNC компонентите да се инициализират след boot.

Стойността идва от:

```json
"adapter_startup_delay_seconds": 90
```

Ако настройката се промени от dashboard configuration, при обновяване на scheduled task delay-ят се записва като PowerShell trigger delay:

```text
PT{seconds}S
```

### 4.3 Стартиране на hidden launcher

`ERPCNCAdapter` стартира:

```text
scripts\launch_adapter_hidden.vbs
```

### 4.4 Стартиране на adapter процеса

`launch_adapter_hidden.vbs` стартира:

```text
erp-cnc-adapter.exe
```

### 4.5 Adapter application startup

След като `erp-cnc-adapter.exe` стартира, приложението изпълнява вътрешна инициализация:

1. Зарежда `config.json`.
2. Инициализира logging.
3. Зарежда CNC client и `cncapi.dll`.
4. Създава `ConnectionManager`.
5. Създава `JobMonitor`.
6. Избира как да стартира CNC runtime според конфигурацията.

## 5. Автоматичен старт: ако Auto-start Eding GUI е изключен

Този режим се използва когато:

```json
"auto_start_eding_gui": false
```

### Последователност

1. `ERPCNCAdapter` стартира `launch_adapter_hidden.vbs`.
2. `launch_adapter_hidden.vbs` стартира `erp-cnc-adapter.exe`.
3. Adapter-ът проверява дали `auto_start_cnc_server` е включено.
4. Adapter-ът стартира `CncServer.exe`, ако не работи.
5. `ConnectionManager` започва опити за връзка към CNC Server.
6. Когато CNC връзката е готова, dashboard health става `connected`.
7. `JobMonitor` започва да следи CNC job state.
8. Ако `show_operator_ready_message` е включено, може да се покаже ready съобщение към оператора.

Важно: в този режим Eding GUI не се стартира автоматично.

Изчаквания в този flow:

- `ConnectionManager` проверява дали `CncServer.exe` процесът е жив с timeout 3 секунди.
- Всеки опит за `connect()` към CNC DLL има timeout 10 секунди.
- Ако връзката не е готова, следващият опит е след `cnc_retry_interval`, стандартно 5 секунди.
- След успешен connect adapter-ът изчаква machine readiness до `cnc_startup_ready_timeout`, стандартно 60 секунди.
- В този readiness loop всяко `get_state()` повикване има timeout 5 секунди.

## 6. Автоматичен старт: ако Auto-start Eding GUI е включен

Този режим се използва когато:

```json
"auto_start_eding_gui": true
```

### Последователност

1. `ERPCNCAdapter` стартира `launch_adapter_hidden.vbs`.
2. `launch_adapter_hidden.vbs` стартира `erp-cnc-adapter.exe`.
3. Adapter-ът се опитва да стартира Eding GUI чрез interactive task/session helper.
4. Adapter-ът не стартира директно `CncServer.exe`, защото Eding GUI трябва да притежава CNC session-а.
5. Adapter-ът изчаква кратко Eding GUI/CNC Server startup window.
6. `ConnectionManager` започва опити за връзка към CNC Server.
7. Когато CNC връзката е готова, dashboard health става `connected`.
8. `JobMonitor` започва да следи CNC job state.

Важно: при автоматичен старт след boot този режим може да зависи от това дали Windows и Eding CNC са напълно готови. Ако машината показва `CNCSERVER = SERVER NOT RESPONDING` след reboot, използвайте manual `START-CNC` flow.

Изчаквания в този flow:

- След стартиране на Eding GUI, adapter-ът изчаква преди да стартира `ConnectionManager`.
- Това изчакване е:

```text
min(max(cnc_retry_interval * 2, 10), 30)
```

- При стандартен `cnc_retry_interval = 5`, изчакването е 10 секунди.
- След това важат стандартните timeouts на `ConnectionManager`: 3 секунди за process check, 10 секунди за `connect()`, 5 секунди за `get_state()`, и до 60 секунди startup readiness timeout.

## 7. Ръчен старт чрез START-CNC

Този режим се използва когато:

```json
"auto_start_adapter_on_logon": false
```

или когато операторът ръчно стартира shortcut-а:

```text
START-CNC
```

Shortcut-ът стартира видим progress прозорец:

```text
scripts\start_cnc_feedback.ps1
```

Този прозорец показва само важни startup съобщения и грешки, а не целия adapter runtime log.

## 8. Manual START-CNC: първи етап

### 8.1 Операторът стартира START-CNC

Първо операторът натиска desktop shortcut:

```text
START-CNC
```

### 8.2 Стартиране на feedback script

Shortcut-ът стартира:

```text
scripts\start_cnc_feedback.ps1
```

Този script показва progress прозорец и стартира elevated manual task:

```text
ERPCNCAdapterManualStart
```

### 8.3 Стартиране на ERPCNCAdapterManualStart

`ERPCNCAdapterManualStart` стартира:

```text
scripts\run_start_cnc_hidden.vbs
```

### 8.4 Стартиране на restart.bat

`run_start_cnc_hidden.vbs` стартира:

```text
scripts\restart.bat
```

с marker:

```text
ERPCNC_MANUAL_TASK=1
```

## 9. Manual START-CNC: reset последователност

`restart.bat` първо почиства старо runtime състояние.

Последователност:

1. Спира `erp-cnc-adapter.exe`, ако работи.
2. Спира Eding GUI процесите:
   - `cnc4.03.exe`
   - `cnc.exe`
3. Спира `CncServer.exe`, ако работи.
4. Изчаква кратко, за да приключат процесите.
5. Прочита `config.json`, за да провери `auto_start_eding_gui`.

Точни изчаквания:

- След спиране на adapter, Eding GUI и `CncServer.exe`, `restart.bat` изчаква 2 секунди.
- Това изчакване позволява на Windows да освободи процесите, DLL handles и task state преди следващ старт.

## 10. Manual START-CNC: ако Auto-start Eding GUI е включен

Този режим се използва когато:

```json
"auto_start_eding_gui": true
```

### Последователност

1. `restart.bat` спира стария adapter, Eding GUI и `CncServer.exe`.
2. `restart.bat` прочита `config.json`.
3. Понеже `auto_start_eding_gui` е включено, `restart.bat` стартира Eding GUI преди adapter-а.
4. Стартирането на Eding GUI се изпълнява чрез:

```text
scripts\start_eding_handoff.ps1
```

5. `start_eding_handoff.ps1` намира Eding GUI executable до `cncapi.dll`.
6. Стартира Eding GUI:

```text
C:\CNC4.03\cnc.exe
```

или друг намерен Eding executable, например:

```text
C:\CNC4.03\cnc4.03.exe
```

7. `restart.bat` изчаква около 15 секунди, за да може Eding GUI да стартира CNC Server.
8. След това `restart.bat` стартира adapter-а чрез задачата:

```text
ERPCNCAdapter
```

9. Ако `ERPCNCAdapter` е disabled, `restart.bat` използва fallback:

```text
scripts\launch_adapter_hidden.vbs
```

10. Adapter-ът стартира и вижда, че Eding/CNC Server вече се инициализира.
11. `ConnectionManager` започва опити за връзка.
12. `start_cnc_feedback.ps1` polling-ва:

```text
http://127.0.0.1:8002/api/health
```

13. Когато health endpoint върне `cnc.connected = true`, progress прозорецът показва, че `START-CNC` е готов.

Това е предпочитаната manual последователност при машини, където Eding трябва да притежава CNC Server session-а.

Изчаквания в този flow:

- `restart.bat` изчаква 2 секунди след спиране на старите процеси.
- `start_eding_handoff.ps1` при нужда спира стар `CncServer.exe` и изчаква 2 секунди преди `Start-Process` за Eding GUI.
- След успешно стартиране на Eding GUI, `restart.bat` изчаква 15 секунди преди да стартира adapter-а.
- `start_cnc_feedback.ps1` изчаква adapter readiness до 90 секунди за един опит.
- Ако adapter-ът не стане готов, `START-CNC` прави до 3 пълни опита.
- Между пълните опити има 5 секунди изчакване.
- Health polling към `/api/health` е през 2 секунди.
- Всяка health заявка има timeout 2 секунди.

## 11. Manual START-CNC: ако Auto-start Eding GUI е изключен

Този режим се използва когато:

```json
"auto_start_eding_gui": false
```

### Последователност

1. `restart.bat` спира стария adapter, Eding GUI и `CncServer.exe`.
2. `restart.bat` създава one-shot marker файл:

```text
manual_start_defer_gui.flag
```

3. `restart.bat` стартира adapter-а чрез:

```text
ERPCNCAdapter
```

4. Ако `ERPCNCAdapter` е disabled, се използва fallback:

```text
scripts\launch_adapter_hidden.vbs
```

5. Adapter-ът консумира `manual_start_defer_gui.flag`.
6. Adapter-ът не стартира Eding GUI.
7. Adapter-ът стартира `CncServer.exe`, ако `auto_start_cnc_server` е включено.
8. `ConnectionManager` започва опити за връзка.
9. `start_cnc_feedback.ps1` polling-ва `/api/health`.
10. Когато `cnc.connected = true`, progress прозорецът показва, че `START-CNC` е готов.

Изчаквания в този flow:

- `restart.bat` изчаква 2 секунди след спиране на старите процеси.
- `start_cnc_feedback.ps1` изчаква adapter readiness до 90 секунди за един опит.
- Ако adapter-ът не стане готов, `START-CNC` прави до 3 пълни опита.
- Между пълните опити има 5 секунди изчакване.
- Health polling към `/api/health` е през 2 секунди.
- Всяка health заявка има timeout 2 секунди.
- Adapter-ът използва стандартните `ConnectionManager` timeouts: 3 секунди за process check, 10 секунди за `connect()`, 5 секунди за `get_state()`, и `cnc_retry_interval` между опитите.

## 12. Ред на вътрешна adapter инициализация

След като `erp-cnc-adapter.exe` стартира, вътрешният ред е:

1. `Settings` зарежда стойности от `config.json`.
2. Logging се инициализира.
3. `AppState` се създава.
4. Стар PID файл се проверява и stale adapter процес може да бъде спрян.
5. CNC client се инициализира.
6. `ConnectionManager` се създава.
7. `JobMonitor` се създава.
8. Adapter startup избира runtime path:
   - Eding GUI path;
   - директен `CncServer.exe` path;
   - manual defer path.
9. `ConnectionManager` започва background loop.
10. `JobMonitor` започва background monitoring.

## 13. Timers, delays и polling интервали

Тази секция обобщава всички важни изчаквания и интервали в startup логиката.

| Компонент | Стойност по подразбиране | Кога се използва |
|---|---:|---|
| `adapter_startup_delay_seconds` | 90 секунди | Delay на `ERPCNCAdapter` scheduled task при Windows logon/startup |
| `restart.bat` process cleanup wait | 2 секунди | След спиране на adapter, Eding GUI и `CncServer.exe` |
| Manual auto-GUI wait before adapter | 15 секунди | След стартиране на Eding GUI, преди да се стартира adapter-ът |
| `start_eding_handoff.ps1` server cleanup wait | 2 секунди | След спиране на стар `CncServer.exe`, преди старт на Eding GUI |
| `start_cnc_feedback.ps1` readiness timeout | 90 секунди | Максимално време за един START-CNC опит |
| `start_cnc_feedback.ps1` max attempts | 3 опита | Максимален брой пълни START-CNC опита |
| Retry wait between START-CNC attempts | 5 секунди | Пауза между пълните manual startup опити |
| `/api/health` polling interval | 2 секунди | Колко често START-CNC проверява adapter readiness |
| `/api/health` request timeout | 2 секунди | Timeout за една health HTTP заявка |
| `cnc_retry_interval` | 5 секунди | Пауза между CNC connection retry опити |
| CNC process check timeout | 3 секунди | Timeout за проверка дали `CncServer.exe` процесът е жив |
| CNC `connect()` timeout | 10 секунди | Timeout за DLL connect call |
| CNC `get_state()` timeout | 5 секунди | Timeout за проверка на interpreter state |
| `cnc_startup_ready_timeout` | 60 секунди | Максимално време за изчакване CNC да стане ready след connect |
| `cnc_health_interval` | 10 секунди | Heartbeat интервал след успешна връзка |
| Heartbeat process check timeout | 3 секунди | Timeout за heartbeat проверка на `CncServer.exe` |
| Heartbeat connection check timeout | 5 секунди | Timeout за heartbeat `is_server_connected()` |
| `job_monitor_poll_interval` | 1 секунда | Колко често `JobMonitor` проверява job status |
| Job done report HTTP timeout | 10 секунди | Timeout при изпращане на job done report към ERP |
| `ERPCNCAdapterWatchdog` schedule | 2 минути | Колко често watchdog task проверява adapter-а |
| Scheduled task restart interval | 1 минута | Windows Task Scheduler restart interval за `ERPCNCAdapter` |
| Scheduled task restart count | 3 опита | Колко restart опита Task Scheduler може да направи |

Забележка: част от стойностите са configurable през dashboard (`adapter_startup_delay_seconds`, `cnc_retry_interval`, `cnc_health_interval`, `cnc_startup_ready_timeout`, `job_monitor_poll_interval`). Останалите са hardcoded в startup scripts.

## 14. Health readiness

Adapter-ът се счита за готов, когато:

```json
"cnc": {
  "connected": true
}
```

в endpoint-а:

```text
http://127.0.0.1:8002/api/health
```

`START-CNC` не затваря progress прозореца само защото процесът е стартиран. Той изчаква adapter health endpoint да потвърди CNC връзката.

## 15. Обобщение на реда

### Auto logon, без Eding GUI

```text
Windows logon
-> ERPCNCAdapter
-> launch_adapter_hidden.vbs
-> erp-cnc-adapter.exe
-> CncServer.exe
-> ConnectionManager
-> JobMonitor
-> /api/health connected
```

### Auto logon, с Eding GUI

```text
Windows logon
-> 90s scheduled task delay
-> ERPCNCAdapter
-> launch_adapter_hidden.vbs
-> erp-cnc-adapter.exe
-> Eding GUI
-> Eding-owned CncServer.exe
-> 10-30s ConnectionManager GUI delay
-> JobMonitor
-> /api/health connected
```

### Manual START-CNC, с Eding GUI

```text
START-CNC shortcut
-> start_cnc_feedback.ps1
-> ERPCNCAdapterManualStart
-> run_start_cnc_hidden.vbs
-> restart.bat
-> stop old adapter / Eding GUI / CncServer
-> 2s cleanup wait
-> start_eding_handoff.ps1
-> Eding GUI
-> 15s wait for Eding startup
-> ERPCNCAdapter or launch_adapter_hidden.vbs fallback
-> erp-cnc-adapter.exe
-> ConnectionManager
-> JobMonitor
-> /api/health connected
```

### Manual START-CNC, без Eding GUI

```text
START-CNC shortcut
-> start_cnc_feedback.ps1
-> ERPCNCAdapterManualStart
-> run_start_cnc_hidden.vbs
-> restart.bat
-> stop old adapter / Eding GUI / CncServer
-> 2s cleanup wait
-> manual_start_defer_gui.flag
-> ERPCNCAdapter or launch_adapter_hidden.vbs fallback
-> erp-cnc-adapter.exe
-> CncServer.exe
-> ConnectionManager
-> JobMonitor
-> /api/health connected
```

## 16. Важни бележки

- `ERPCNCAdapter` е основната задача за adapter процеса.
- `ERPCNCAdapterManualStart` е входната точка за ръчен старт.
- `START-CNC` показва feedback, но privileged действията се изпълняват през scheduled tasks.
- Когато Eding GUI трябва да се стартира автоматично, manual flow стартира Eding преди adapter-а.
- Когато Eding GUI е изключен, adapter-ът може директно да стартира `CncServer.exe`.
- `auto_start_adapter_on_logon` управлява дали Windows стартира adapter-а автоматично.
- `auto_start_eding_gui` управлява дали Eding GUI участва в runtime startup последователността.
