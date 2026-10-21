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

Requirements: [uv](https://docs.astral.sh/uv/) and Python 3.11 or later. macOS, Linux and Windows are targeted;
see [Known limitations](#known-limitations) for what has actually been verified.

```
git clone https://github.com/Raphael-Barret/mail-mcp.git
cd mail-mcp
uv sync
uv run pytest
```

## Configuration

1. Copy `config.example.toml` to the configuration file (or set `MAIL_MCP_CONFIG`) and describe your accounts.
   One `[accounts.<name>]` entry is enough to add an account. Default location:

   | System | File |
   |---|---|
   | macOS, Linux | `$XDG_CONFIG_HOME/mail-mcp/config.toml`, otherwise `~/.config/mail-mcp/config.toml` |
   | Windows | `%APPDATA%\mail-mcp\config.toml` |

2. Store each account's password in the system keychain, typed with no echo (nothing lands in your shell
   history). The account name is the one used in the configuration:

   ```
   uv run mail-mcp set-secret <account-name>
   ```

   Run it in a real terminal, not inside an assistant session.
   - **macOS**: Keychain. If you get "User interaction is not allowed", unlock it first:
     `security unlock-keychain ~/Library/Keychains/login.keychain-db`.
   - **Windows**: Credential Manager, nothing to install.
   - **Linux**: a running, unlocked Secret Service (gnome-keyring or KWallet) is required. Without one (a
     headless server, for instance), storing the secret fails with an explicit message.
3. Restart the server after every configuration change (it is read at startup).

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

An account is four lines of configuration and a password in the keychain: no code to write.

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

## Registering in Claude Code

```
claude mcp add --scope user mail -- uv run --directory /path/to/mail-mcp mail-mcp
```

On Windows, give the Windows path of the folder (`C:\path\to\mail-mcp`).

The `user` scope keeps the declaration out of the repository. Restart Claude Code; `/mcp` should then list
`mail`.

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
