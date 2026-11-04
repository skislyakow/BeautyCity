# Скиллы Matt Pocock — локальная установка

Скиллы **не хранятся в репозитории BeautyCity** и не коммитятся в GitHub.
Они лежат в отдельной локальной папке и подключаются глобально в OpenCode,
поэтому доступны в любом проекте на этой машине.

Источник: <https://github.com/mattpocock/skills>

## 1. Клонировать скиллы

Windows (PowerShell):

```powershell
$dest = "$HOME\agent-skills\mattpocock-skills"
git clone --depth 1 https://github.com/mattpocock/skills.git $dest
```

Linux / macOS:

```bash
git clone --depth 1 https://github.com/mattpocock/skills.git "$HOME/agent-skills/mattpocock-skills"
```

## 2. Подключить в OpenCode

Откройте глобальный конфиг:

- Windows: `C:\Users\<user>\.config\opencode\opencode.jsonc`
- Linux / macOS: `~/.config/opencode/opencode.jsonc`

и добавьте пути к папкам со скиллами:

```jsonc
{
  "skills": [
    "<путь>/skills/engineering",
    "<путь>/skills/productivity"
  ]
}
```

Пример для текущей машины:

```jsonc
{
  "skills": [
    "C:/code/agent-skills/mattpocock-skills/skills/engineering",
    "C:/code/agent-skills/mattpocock-skills/skills/productivity"
  ]
}
```

После изменения конфига перезапустите OpenCode.

## 3. Обновить скиллы

```bash
git -C <путь-к-скиллам> pull --ff-only
```

## 4. Проверить

В OpenCode должны быть доступны скиллы:

- `code-review`
- `improve-codebase-architecture`
- `tdd`
- `diagnosing-bugs`
- `grilling`
- `domain-modeling`
- и остальные из `skills/engineering` и `skills/productivity`

Проверка: вызвать `/code-review` в новом чате.

## Важно

- Папку со скиллами **не добавлять в git** и не коммитить в BeautyCity.
- На другой машине достаточно повторить шаги 1–2.
- Если на машине нет `git`/`uv`, сначала установите их.
- Локальные helper-скрипты (если они есть на машине) лежат вне репозитория,
  например `C:\code\agent-skills\setup.ps1` и `setup.sh`.
