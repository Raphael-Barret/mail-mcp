# mail-mcp

[English](README.md) | **Français**

Serveur [MCP](https://modelcontextprotocol.io) local qui donne à un assistant (Claude Code, par exemple)
un accès à plusieurs boîtes mail, **en lecture seule par défaut**.

- Plusieurs comptes, un format de sortie unique (compte, id, expéditeur, sujet, date, non lu, extrait).
- Les secrets restent dans le trousseau du système (macOS Keychain, Windows Credential Manager, Secret Service
  sous Linux), jamais dans un fichier ni dans le dépôt.
- Les écritures (brouillon, archivage) sont des capacités distinctes, désactivées par défaut,
  activées compte par compte dans la configuration, jamais par un argument d'outil.
- Le contenu des mails est traité comme une donnée non fiable, et chaque sortie d'outil le signale.

État actuel : backend IMAP (Gmail et serveurs IMAP à mot de passe). Prévus : Gmail API, Microsoft Graph
(voir [Limites connues](#limites-connues)).

## Installation

Les étapes 1, 3 et 5 diffèrent selon le système, les autres sont identiques partout. Les commandes marquées
**Windows** sont pour PowerShell.

### 1. Installer les prérequis

Il faut [Git](https://git-scm.com) et [uv](https://docs.astral.sh/uv/). Pas besoin d'installer Python vous-même :
uv télécharge une version adaptée (3.11 ou plus) quand il en a besoin.

**macOS** (avec [Homebrew](https://brew.sh)) :

```
brew install git uv
```

**Linux** : installer git avec le gestionnaire de paquets (`sudo apt install git`, `sudo dnf install git`, ...),
puis uv :

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** :

```
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Fermer puis rouvrir PowerShell ensuite pour que `git` et `uv` soient trouvés. Vérifier avec `git --version` et
`uv --version`.

### 2. Récupérer le code et lancer les tests

Identique sur tous les systèmes :

```
git clone https://github.com/Raphael-Barret/mail-mcp.git
cd mail-mcp
uv sync
uv run pytest
```

Tous les tests doivent passer. Ils n'utilisent aucun compte réel.

### 3. Créer le fichier de configuration

L'emplacement par défaut dépend du système. Définir `MAIL_MCP_CONFIG` pour en utiliser un autre.

**macOS et Linux** (`$XDG_CONFIG_HOME` est respecté s'il est défini) :

```
mkdir -p ~/.config/mail-mcp
cp config.example.toml ~/.config/mail-mcp/config.toml
nano ~/.config/mail-mcp/config.toml
```

**Windows** :

```
New-Item -ItemType Directory -Force "$env:APPDATA\mail-mcp" | Out-Null
Copy-Item config.example.toml "$env:APPDATA\mail-mcp\config.toml"
notepad "$env:APPDATA\mail-mcp\config.toml"
```

L'éditer pour décrire vos comptes (voir [Configurer les comptes](#configurer-les-comptes)). Une entrée
`[accounts.<nom>]` par compte. Les mots de passe ne vont jamais dans ce fichier.

### 4. Ranger chaque mot de passe dans le trousseau du système

Pour chaque compte de la configuration, lancer ceci dans un vrai terminal (pas dans une session d'assistant).
Le mot de passe est saisi sans écho, il ne finit donc pas dans l'historique du shell :

```
uv run mail-mcp set-secret <nom-du-compte>
```

Où il est rangé, et ce qu'il faut savoir :

- **macOS** : le trousseau de session. Si « User interaction is not allowed » apparaît, le déverrouiller d'abord
  avec `security unlock-keychain ~/Library/Keychains/login.keychain-db`.
- **Windows** : le Gestionnaire d'identifiants (Credential Manager). Rien à installer ni à déverrouiller.
- **Linux avec session de bureau (GNOME, KDE)** : le service de trousseau tourne normalement et est déverrouillé
  à l'ouverture de session.
- **Linux sans bureau (SSH, serveur, conteneur)** : il n'y a pas de service de trousseau, et `set-secret` échoue
  avec un message explicite. Il faut en démarrer un dans une session D-Bus, depuis le shell qui lancera aussi
  votre assistant (exemple Debian et Ubuntu ; cette séquence a été testée dans un conteneur) :

  ```
  sudo apt install gnome-keyring dbus
  dbus-run-session -- bash
  eval $(printf '%s' 'choisir-un-mot-de-passe-de-trousseau' | gnome-keyring-daemon --unlock --components=secrets)
  uv run mail-mcp set-secret <nom-du-compte>
  ```

  Continuer ensuite dans ce même shell et y lancer Claude Code : le serveur lit le secret par la même session
  D-Bus.

### 5. Enregistrer le serveur dans Claude Code

À lancer depuis le dossier `mail-mcp`. La commande est la même sur macOS, Linux et Windows (PowerShell).
La portée `user` garde la déclaration hors du dépôt.

```
claude mcp add --scope user mail -- uv run --directory "$PWD" mail-mcp
```

(`$PWD` est le dossier courant dans ces shells. Le chemin est enregistré tel quel : refaire l'enregistrement
si le projet est déplacé.)

### 6. Vérifier que ça marche

Relancer Claude Code, puis ouvrir `/mcp` : `mail` doit apparaître comme connecté. Demander à l'assistant
d'exécuter `list_accounts`, puis `list_messages` sur un compte. Après chaque changement de configuration,
redémarrer le serveur (`/mcp`, ou relancer Claude Code) : la configuration est lue au démarrage.

## Configurer les comptes

### Gmail

Activer la validation en deux étapes, puis créer un **mot de passe d'application** sur
<https://myaccount.google.com/apppasswords>. C'est lui qu'on range dans le trousseau. Hôte `imap.gmail.com`,
port 993, `security = "ssl"`. Chez Gmail, archiver retire le message du dossier INBOX : il reste dans
« Tous les messages » (vérifié avant de le retirer).

### Autre serveur IMAP (école, entreprise)

Les paramètres sont souvent publiés dans un fichier d'autoconfiguration :
`https://autoconfig.<domaine>/mail/config-v1.1.xml` (hôte, port, sécurité, forme de l'identifiant).
Sinon, les lire dans les réglages du compte de votre client mail. Pour archiver sur un serveur sans dossier
d'archive reconnu, créer le dossier dans votre client et le nommer dans `archive_folder`.

### Ajouter un compte

Un compte, c'est quelques lignes de configuration et un mot de passe dans le trousseau : aucun code à écrire.

```toml
[accounts.ecole]
backend = "imap"
host = "imap.exemple.edu"
port = 993
security = "ssl"
username = "prenom.nom@exemple.edu"
```

Ça marche pour tout serveur IMAP qui accepte un mot de passe (Dovecot, Zimbra, Cyrus, serveurs d'école ou
d'entreprise). Ça ne marche **pas** quand l'établissement est sur Microsoft 365 ou Google Workspace avec
l'authentification par mot de passe désactivée : il faut alors OAuth, que ce serveur ne gère pas encore.

## Dépannage

| Symptôme | Cause et correction |
|---|---|
| `git` ou `uv` introuvable (Windows) | Fermer et rouvrir PowerShell après `winget install`. |
| `mail` en échec ou absent dans `/mcp` | Vérifier que le serveur démarre : `uv run mail-mcp` dans le dossier du projet. Si Claude Code ne trouve pas `uv`, enregistrer avec le chemin complet de `uv` (`which uv`, ou `(Get-Command uv).Source` sous Windows). |
| « Config introuvable » | Le fichier de configuration n'est pas où l'indique le tableau de l'étape 3. Le créer, ou définir `MAIL_MCP_CONFIG`. |
| « Aucun secret dans le trousseau » | Lancer `uv run mail-mcp set-secret <nom-du-compte>` avec exactement le nom de la configuration. |
| « Trousseau indisponible » (Linux) | Aucun service de trousseau ne tourne, ou il est verrouillé : voir l'étape 4. |
| « User interaction is not allowed » (macOS) | Le trousseau est verrouillé pour ce terminal : voir l'étape 4. |
| Gmail refuse la connexion | La validation en deux étapes doit être active et le mot de passe doit être un mot de passe d'application, pas celui de votre compte Google. L'IMAP doit être activé dans les paramètres Gmail. |
| Outils absents ou compte non listé après un changement | La configuration est lue au démarrage : redémarrer le serveur. |
| « Identifiant périmé » | Le dossier a changé sur le serveur : le relister pour obtenir des identifiants frais. |

## Outils

| Outil | Effet | Disponible |
|---|---|---|
| `list_accounts` | comptes configurés et capacités d'écriture | toujours |
| `list_messages` | derniers messages d'un dossier | toujours |
| `search_messages` | recherche plein texte | toujours |
| `read_message` | lit un message | toujours |
| `read_thread` | lit le fil (par `Message-ID` et `References`, dossier courant) | toujours |
| `create_draft` | crée un brouillon, **sans l'envoyer** ; peut répondre à un message | si un compte a `allow = ["draft"]` |
| `archive_message` | sort un message de la boîte de réception, sans le supprimer | si un compte a `allow = ["archive"]` |

Chaque appel d'écriture revérifie la configuration du compte visé. Il n'existe pas d'outil pour envoyer ni
supprimer.

## Modèle de sécurité

- **Lecture seule vérifiable.** La connexion de lecture n'ouvre les dossiers qu'avec `EXAMINE` et lit avec
  `BODY.PEEK` : rien n'est marqué comme lu. Elle n'a aucune commande d'écriture, et un test le prouve.
- **Écriture limitée.** La connexion d'écriture est une classe à part. Elle ne sait faire que : ajouter un
  brouillon, déplacer un message, ou retirer un seul message du dossier courant une fois qu'il existe
  ailleurs (copie réussie, ou présence vérifiée dans « Tous les messages » chez Gmail). Elle refuse si un
  autre message du dossier est déjà marqué supprimé. Aucun chemin de code ne supprime un message
  qui n'existe pas ailleurs.
- **Brouillon, jamais envoi.** Un brouillon part dans le dossier Brouillons ; c'est vous qui l'envoyez.
  Les adresses et l'objet sont refusés s'ils contiennent un saut de ligne (injection d'en-têtes).
- **Contenu non fiable.** Un mail peut contenir des instructions à l'intention de l'assistant. Les sorties de
  lecture sont enveloppées dans un avertissement, mais la défense reste côté usage : ne pas mettre les outils
  d'écriture en autorisation automatique, relire les brouillons.
- **Les identifiants ne sont pas limités.** Un mot de passe d'application ou un mot de passe de compte donne
  tous les droits côté serveur. La lecture seule ne tient que par ce code et votre configuration.

## Limites connues

- **Microsoft 365 et Google Workspace sans mot de passe IMAP** : non supportés (OAuth requis). Les backends
  Gmail API et Graph sont prévus, pas écrits.
- **Vérifié en réel** : lecture, recherche, brouillon et archivage sur Gmail ; lecture et brouillon sur un
  serveur d'école. Le chemin d'archivage pour un serveur sans `MOVE` (copie puis retrait) n'est couvert que
  par des tests avec fausse connexion IMAP.
- **Systèmes** : macOS utilisé au quotidien. Linux : tests et démarrage du serveur MCP vérifiés dans un conteneur
  (Python 3.11, 3.12, 3.13), mais sans comptes réels ni trousseau graphique. Windows : couvert par la CI
  (`.github/workflows/ci.yml`), jamais essayé avec un vrai compte.
- **Recherche** : texte intégral (`TEXT`), floue chez Gmail ; pas de syntaxe de recherche propre à Gmail.
- **Fils de discussion** : reconstitués dans le dossier courant seulement.
- **Brouillons** : texte brut, sans pièce jointe. Pas d'envoi ni de suppression, par choix.
- **Noms de dossier** : ceux détectés par le serveur fonctionnent ; un nom saisi à la main avec des accents
  doit être donné dans l'encodage IMAP (UTF-7 modifié).
- **Pièces jointes** : non lues.
- **Langue** : les messages renvoyés par les outils, les commentaires et les docstrings du code sont en français.

## Développement

```
uv run pytest
```

Ajouter un backend : implémenter `MailBackend` (et `DraftingBackend` / `ArchivingBackend` s'il écrit), puis
l'enregistrer dans `mail_mcp.registry.BACKENDS`.

## Licence

MIT, voir `LICENSE`.
