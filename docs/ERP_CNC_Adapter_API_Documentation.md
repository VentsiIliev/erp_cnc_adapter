# ERP-CNC Adapter — API Документация

Този документ описва всички налични API заявки на ERP-CNC Adapter сървъра, техните параметри, структура на заявката и структура на отговора.

---

## 1. Статус на задачата (Job Status)

| Параметър | Стойност |
|---|---|
| HTTP метод | `GET` |
| Път (URL) | `/api/cnc/job/status` |
| Описание | Връща текущото състояние на CNC машината и информация за заредената задача. |
| Тяло на заявката | Няма |
| Автентикация | Не се изисква |

### Отговор (Response)

**HTTP статус:** 200 OK

| Поле | Тип | Описание |
|---|---|---|
| `state` | int | Код на текущото състояние на CNC интерпретатора (0–23). |
| `stateText` | string | Текстово описание на състоянието (напр. "Ready", "Running job"). |
| `jobName` | string | Пълен път до заредения файл със задачата. |
| `jobLoadCounter` | int | Брояч на заредените задачи. |
| `numLinesInJob` | int | Брой редове в задачата. |
| `numLinesInMacro` | int | Брой редове в макроса. |
| `numLinesInUserMacro` | int | Брой редове в потребителския макрос. |
| `isLongJob` | int | Флаг — задачата е дълга (1) или не (0). |
| `isSuperLongJob` | int | Флаг — задачата е много дълга (1) или не (0). |
| `jobIsRendered` | int | Флаг — задачата е визуализирана (1) или не (0). |
| `totalJobLength` | float | Обща дължина на задачата (в мм). |
| `jobProgress` | float | Прогрес на изпълнението (в процент). |
| `jobActualRunningTime` | float | Реално изминало време на работа (в секунди). |
| `jobRemainingRunningTime` | float | Оставащо време за изпълнение (в секунди). |
| `jobEstimatedTime` | float | Прогнозно общо време (в секунди). |
| `TCACollision` | int | Флаг за TCA колизия. |
| `MCACollision` | int | Флаг за MCA колизия. |
| `xCollision` | int | Флаг за колизия по ос X. |
| `yCollision` | int | Флаг за колизия по ос Y. |
| `zCollision` | int | Флаг за колизия по ос Z. |
| `jobRenderLine` | int | Текущ ред при визуализация. |
| `jobRenderProgressPercentage` | float | Прогрес на визуализацията (в процент). |
| `curIpLine` | int | Текущ ред на интерпретатора. |
| `curExLine` | int | Текущ изпълняван ред. |
| `lastKnownExecutedLineNumber` | int | Последен известен изпълнен ред. |
| `lastKnownToolChangeLineNumber` | int | Последен ред със смяна на инструмент. |
| `doRepeatJob` | int | Флаг за повторение на задачата. |
| `nrOfJobRepeatsSet` | int | Зададен брой повторения. |
| `nrOfRepeatsActual` | int | Реален брой извършени повторения. |
| `extraLineWhenEndOfJob` | string | Допълнителен ред при край на задачата. |
| `stockDiameterTurning` | float | Диаметър на заготовката (стругарство). |
| `stockLengthTurning` | float | Дължина на заготовката (стругарство). |
| `stockZAtWorkOffset` | int | Z позиция на заготовката спрямо работния офсет. |

### Таблица на състоянията (state)

Полето `state` може да има следните стойности:

| Код | Описание |
|---|---|
| 0 | Power-up — Начално захранване / инициализация |
| 1 | Idle — Неактивен |
| 2 | Ready — Готов за работа |
| 3 | Execution error — Грешка при изпълнение |
| 4 | Internal error — Вътрешна грешка |
| 5 | Aborted — Прекъснат |
| 6 | Running job — Изпълнява задача |
| 7 | Running line — Изпълнява единичен ред |
| 8 | Running sub — Изпълнява подпрограма |
| 9 | Running sub search — Търсене в подпрограма |
| 10 | Running line search — Търсене в ред |
| 11 | Paused (line) — Пауза (ред) |
| 12 | Paused (job) — Пауза (задача) |
| 13 | Paused (sub) — Пауза (подпрограма) |
| 14 | Paused (line search) — Пауза (търсене в ред) |
| 15 | Paused (sub search) — Пауза (търсене в подпрограма) |
| 16 | Running handwheel — Ръчно колело |
| 17 | Running line handwheel — Ред с ръчно колело |
| 18 | Running line paused — Ред на пауза |
| 19 | Running axis jog — Ръчно придвижване по ос |
| 20 | Running IP jog — IP придвижване |
| 21 | Rendering graph — Визуализиране на графика |
| 22 | Searching — Търсене |
| 23 | Search done — Търсенето завърши |

### Примерен отговор

```json
{
  "state": 2,
  "stateText": "Ready",
  "jobName": "\\\\192.168.2.11\\Production\\CNC\\Mills\\job.nc",
  "jobLoadCounter": 1,
  "numLinesInJob": 245,
  "numLinesInMacro": 0,
  "numLinesInUserMacro": 0,
  "isLongJob": 0,
  "isSuperLongJob": 0,
  "jobIsRendered": 1,
  "totalJobLength": 1234.56,
  "jobProgress": 0.0,
  "jobActualRunningTime": 0.0,
  "jobRemainingRunningTime": 0.0,
  "jobEstimatedTime": 120.0,
  "TCACollision": 0,
  "MCACollision": 0,
  "xCollision": 0,
  "yCollision": 0,
  "zCollision": 0,
  "jobRenderLine": 245,
  "jobRenderProgressPercentage": 100.0,
  "curIpLine": 0,
  "curExLine": 0,
  "lastKnownExecutedLineNumber": 0,
  "lastKnownToolChangeLineNumber": 0,
  "doRepeatJob": 0,
  "nrOfJobRepeatsSet": 0,
  "nrOfRepeatsActual": 0,
  "extraLineWhenEndOfJob": "",
  "stockDiameterTurning": 0.0,
  "stockLengthTurning": 0.0,
  "stockZAtWorkOffset": 0
}
```

---

## 2. Зареждане на задача (Load Job)

| Параметър | Стойност |
|---|---|
| HTTP метод | `POST` |
| Път (URL) | `/api/cnc/job/load` |
| Описание | Зарежда G-code файл (задача) в CNC интерпретатора. |
| Content-Type | `application/json` |
| Автентикация | Не се изисква |

### Тяло на заявката (Request Body)

| Поле | Тип | Задължително | Описание |
|---|---|---|---|
| `fileName` | string | Да | Пълен път до файла със задачата. Наклонените черти (`/`) автоматично се преобразуват в обратни (`\`). Минимална дължина: 1 символ. |

### Примерна заявка

```json
{
  "fileName": "\\\\192.168.2.11\\Production\\CNC\\Mills\\job.nc"
}
```

### Отговор (Response)

**HTTP статус:** 200 OK (при успех или DLL грешка)

| Поле | Тип | Описание |
|---|---|---|
| `status` | int | Код на резултата: 0 = успех, друга стойност = грешка. |
| `message` | string | Описание на резултата (напр. "Job loaded successfully"). |
| `fileName` | string | Пътят до файла, който е бил зареден. |

### Примерен успешен отговор

```json
{
  "status": 0,
  "message": "Job loaded successfully",
  "fileName": "\\\\192.168.2.11\\Production\\CNC\\Mills\\job.nc"
}
```

### Примерен отговор при грешка

```json
{
  "status": 3,
  "message": "Load failed with error code: 3",
  "fileName": "\\\\192.168.2.11\\Production\\CNC\\Mills\\job.nc"
}
```

---

## 3. Стартиране на задача (Start Job)

| Параметър | Стойност |
|---|---|
| HTTP метод | `POST` |
| Път (URL) | `/api/cnc/job/start` |
| Описание | Стартира (или възобновява) изпълнението на заредената задача. CNC машината трябва да е в състояние Ready (код 2) преди извикване. |
| Тяло на заявката | Няма |
| Автентикация | Не се изисква |

### Отговор (Response)

**HTTP статус:** 200 OK

| Поле | Тип | Описание |
|---|---|---|
| `status` | int | Код на резултата: 0 = успех, друга стойност = грешка. |
| `message` | string | Описание на резултата (напр. "Job started successfully"). |

### Примерен успешен отговор

```json
{
  "status": 0,
  "message": "Job started successfully"
}
```

### Примерен отговор при грешка

```json
{
  "status": 3,
  "message": "Start failed with error code: 3"
}
```

---

## Забележки

1. Всички заявки се изпращат към базовия адрес на сървъра (по подразбиране `http://127.0.0.1:8000`).
2. При рестартиране на адаптера, ако CNC машината е в състояние Power-up, автоматично се изпраща команда `CncReset` за преминаване в Ready.
3. Swagger документацията е достъпна на адрес `/docs` (напр. `http://127.0.0.1:8000/docs`).
4. Преди стартиране на задача (`POST /api/cnc/job/start`) е необходимо задачата да е заредена (`POST /api/cnc/job/load`) и CNC машината да е в състояние Ready (код 2).
