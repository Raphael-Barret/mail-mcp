# mail-mcp

**English** | [Français](LISEZMOI.md)

A local [MCP](https://modelcontextprotocol.io) server that gives an assistant (Claude Code, for example) access
to several mailboxes, **read-only by default**.

- Several accounts, one output format (account, id, sender, subject, date, unread, snippet).
- Secrets stay in the system keychain (macOS Keychain, Windows Credential Manager, Secret Service on Linux),
  never in a file or in the repository.
- Writes (drafts, archiving) are separate capabilities, off by default, enabled account by account in the
  configuration, never through a tool argument.
- Mail content is treated as untrusted data, and every tool output says so.

Current state: IMAP backend (Gmail and any IMAP server that accepts a password). Planned: Gmail API,
Microsoft Graph (see [Known limitations](#known-limitations)).

## Installation

Steps 1, 3 and 5 differ by system; the others are identical everywhere. Commands labelled **Windows** are for
PowerShell.

### 1. Install the prerequisites

You need [Git](https://git-scm.com) and [uv](https://docs.astral.sh/uv/). You do not have to install Python
yourself: uv downloads a suitable version (3.11 or later) when it is needed.

**macOS** (with [Homebrew](https://brew.sh)):

```
brew install git uv
```

**Linux**: install git with your package manager (`sudo apt install git`, `sudo dnf install git`, ...), then uv:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**:

```
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Close and reopen PowerShell afterwards so that `git` and `uv` are found. Check with `git --version` and
`uv --version`.

### 2. Get the code and run the tests

Same on every system:

```
git clone https://github.com/Raphael-Barret/mail-mcp.git
cd mail-mcp
uv sync
uv run pytest
```

All tests should pass. They use no real account.

### 3. Create the configuration file

The default location depends on the system. Set `MAIL_MCP_CONFIG` to use another path.

**macOS and Linux** (`$XDG_CONFIG_HOME` is honoured if set):

```
mkdir -p ~/.config/mail-mcp
cp config.example.toml ~/.config/mail-mcp/config.toml
nano ~/.config/mail-mcp/config.toml
```

**Windows**:

```
New-Item -ItemType Directory -Force "$env:APPDATA\mail-mcp" | Out-Null
Copy-Item config.example.toml "$env:APPDATA\mail-mcp\config.toml"
notepad "$env:APPDATA\mail-mcp\config.toml"
```

Edit it to describe your accounts (see [Setting up accounts](#setting-up-accounts)). One `[accounts.<name>]`
entry per account. Passwords never go in this file.

### 4. Store each password in the system keychain

For every account in the configuration, run this in a real terminal (not inside an assistant session). The
password is typed with no echo, so it never lands in your shell history:

```
uv run mail-mcp set-secret <account-name>
```

Where it is stored, and what to know:

- **macOS**: the login Keychain. If you get "User interaction is not allowed", unlock it first with
  `security unlock-keychain ~/Library/Keychains/login.keychain-db`.
- **Windows**: Credential Manager. Nothing to install or unlock.
- **Linux with a desktop session (GNOME, KDE)**: the keyring service normally runs and is unlocked at login.
- **Linux without a desktop (SSH, server, container)**: there is no keyring service, and `set-secret` fails
  with an explicit message. Start one in a D-Bus session, from the shell that will also run your assistant
  (shown for Debian and Ubuntu; this sequence was tested in a container):

  ```
  sudo apt install gnome-keyring dbus
  dbus-run-session -- bash
  eval $(printf '%s' 'choose-a-keyring-password' | gnome-keyring-daemon --unlock --components=secrets)
  uv run mail-mcp set-secret <account-name>
  ```

  Keep working in that same shell afterwards, and start Claude Code from it: the server reads the secret
  through the same D-Bus session.

### 5. Register the server in Claude Code

Run it from inside the `mail-mcp` folder. The command is the same on macOS, Linux and Windows (PowerShell).
The `user` scope keeps the declaration out of the repository.

```
claude mcp add --scope user mail -- uv run --directory "$PWD" mail-mcp
```

(`$PWD` is the current folder in these shells. The folder path is stored as-is, so register again if you move
the project.)

### 6. Check that it works

Restart Claude Code, then open `/mcp`: `mail` should be listed as connected. Ask the assistant to run
`list_accounts`, then `list_messages` on one account. After every configuration change, restart the server
(`/mcp`, or restart Claude Code): the configuration is read at startup.

## Setting up accounts

### Gmail

Turn on 2-step verification, then create an **app password** at <https://myaccount.google.com/apppasswords>.
That is what goes in the keychain. Host `imap.gmail.com`, port 993, `security = "ssl"`. On Gmail, archiving
removes the message from INBOX: it stays in "All Mail" (checked before it is removed).

### Another IMAP server (school, company)

The settings are often published in an autoconfiguration file:
`https://autoconfig.<domain>/mail/config-v1.1.xml` (host, port, security, username format). Otherwise, read
them from your mail client's account settings. To archive on a server with no recognised archive folder, create
the folder in your mail client and name it in `archive_folder`.

### Adding an account

An account is a few lines of configuration and a password in the keychain: no code to write.

```toml
[accounts.school]
backend = "imap"
host = "imap.example.edu"
port = 993
security = "ssl"
username = "first.last@example.edu"
```

This works for any IMAP server that accepts a password (Dovecot, Zimbra, Cyrus, school and company servers).
It does **not** work when the organisation is on Microsoft 365 or Google Workspace with password authentication
turned off: that requires OAuth, which this server does not handle yet.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `git` or `uv` not found (Windows) | Close and reopen PowerShell after `winget install`. |
| `mail` is failed or absent in `/mcp` | Check the server starts: `uv run mail-mcp` in the project folder. If `uv` is not found by Claude Code, register with the full path of `uv` (`which uv`, or `(Get-Command uv).Source` on Windows). |
| "Config introuvable" | The configuration file is not where the table in step 3 says. Create it, or set `MAIL_MCP_CONFIG`. |
| "Aucun secret dans le trousseau" | Run `uv run mail-mcp set-secret <account-name>` with exactly the name used in the configuration. |
| "Trousseau indisponible" (Linux) | No keyring service is running or it is locked: see step 4. |
| "User interaction is not allowed" (macOS) | The Keychain is locked for this terminal: see step 4. |
| Gmail refuses the login | 2-step verification must be on, and the password must be an app password, not your Google password. IMAP must be enabled in Gmail settings. |
| Tools missing or account not listed after a change | The configuration is read at startup: restart the server. |
| "Identifiant périmé" | The folder changed on the server: list it again to get fresh message ids. |

## Tools

| Tool | Effect | Available |
|---|---|---|
| `list_accounts` | configured accounts and their write capabilities | always |
| `list_messages` | latest messages of a folder | always |
| `search_messages` | full-text search | always |
| `read_message` | reads one message | always |
| `read_thread` | reads the thread (by `Message-ID` and `References`, current folder) | always |
| `create_draft` | creates a draft, **without sending it**; can reply to a message | if an account has `allow = ["draft"]` |
| `archive_message` | takes a message out of the inbox without deleting it | if an account has `allow = ["archive"]` |

Every write call re-checks the configuration of the targeted account. There is no tool to send or delete.

## Security model

- **Verifiable read-only.** The read connection opens folders with `EXAMINE` only and reads with `BODY.PEEK`:
  nothing is marked as read. It has no write command, and a test proves it.
- **Limited writes.** The write connection is a separate class. It can only: append a draft, move a message, or
  remove a single message from the current folder once it exists elsewhere (a successful copy, or presence
  verified in "All Mail" on Gmail). It refuses if another message in the folder is already flagged as deleted.
  No code path deletes a message that does not exist elsewhere.
- **Drafts, never sending.** A draft goes to the Drafts folder; you are the one who sends it. Addresses and
  subject are rejected if they contain a line break (header injection).
- **Untrusted content.** A mail can contain instructions aimed at the assistant. Read outputs are wrapped in a
  warning, but the real defence is in how you use it: do not auto-approve the write tools, and review drafts.
- **Credentials are not scoped.** An app password or an account password grants full rights on the server side.
  Read-only holds only because of this code and your configuration.

## Known limitations

- **Microsoft 365 and Google Workspace without IMAP passwords**: not supported (OAuth required). The Gmail API
  and Graph backends are planned, not written.
- **Verified against real accounts**: reading, searching, drafting and archiving on Gmail; reading and drafting
  on a school server. The archiving path for a server without `MOVE` (copy, then removal) is covered only by
  tests with a fake IMAP connection.
- **Systems**: macOS is used daily. Linux: tests and MCP server startup verified in a container (Python 3.11,
  3.12, 3.13), but with no real accounts and no graphical keychain. Windows: covered by CI
  (`.github/workflows/ci.yml`), never tried with a real account.
- **Search**: full text (`TEXT`), fuzzy on Gmail; no Gmail-specific search syntax.
- **Threads**: rebuilt within the current folder only.
- **Drafts**: plain text, no attachments. No sending and no deletion, by design.
- **Folder names**: names detected from the server work; a name typed by hand with accented characters must be
  given in IMAP encoding (modified UTF-7).
- **Attachments**: not read.
- **Language**: messages returned by the tools, code comments and docstrings are in French.

## Development

```
uv run pytest
```

To add a backend: implement `MailBackend` (and `DraftingBackend` / `ArchivingBackend` if it writes), then
register it in `mail_mcp.registry.BACKENDS`.

## License

MIT, see `LICENSE`.
