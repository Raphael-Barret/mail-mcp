# mail-mcp

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

Prérequis : [uv](https://docs.astral.sh/uv/) et Python 3.11 ou plus. macOS, Linux et Windows sont visés ;
voir [Limites connues](#limites-connues) pour ce qui est réellement vérifié.

```
git clone https://github.com/Raphael-Barret/mail-mcp.git
cd mail-mcp
uv sync
uv run pytest
```

## Configuration

1. Copier `config.example.toml` vers le fichier de configuration (ou définir `MAIL_MCP_CONFIG`) et décrire
   vos comptes. Une entrée `[accounts.<nom>]` suffit pour ajouter un compte. Emplacement par défaut :

   | Système | Fichier |
   |---|---|
   | macOS, Linux | `$XDG_CONFIG_HOME/mail-mcp/config.toml`, sinon `~/.config/mail-mcp/config.toml` |
   | Windows | `%APPDATA%\mail-mcp\config.toml` |

2. Ranger le mot de passe de chaque compte dans le trousseau du système, avec une saisie masquée (rien dans
   l'historique du shell), le nom du compte étant celui de la configuration :

   ```
   uv run mail-mcp set-secret <nom-du-compte>
   ```

   À lancer dans un vrai terminal, pas dans une session d'assistant.
   - **macOS** : Keychain. Si l'erreur « User interaction is not allowed » apparaît, déverrouiller d'abord :
     `security unlock-keychain ~/Library/Keychains/login.keychain-db`.
   - **Windows** : Credential Manager, rien à installer.
   - **Linux** : il faut un service Secret Service actif et déverrouillé (gnome-keyring ou KWallet). Sans lui
     (serveur sans interface graphique), l'enregistrement échoue avec un message explicite.
3. Redémarrer le serveur après chaque changement de configuration (elle est lue au démarrage).

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

Un compte, c'est quatre lignes de configuration et un mot de passe dans le trousseau : aucun code à écrire.

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
## Enregistrement dans Claude Code

```
claude mcp add --scope user mail -- uv run --directory /chemin/vers/mail-mcp mail-mcp
```

Sous Windows, donner le chemin Windows du dossier (`C:\chemin\vers\mail-mcp`).

La portée `user` garde la déclaration hors du dépôt. Relancer Claude Code, puis `/mcp` doit montrer `mail`.

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
  autre message du dossier est déjà marqué supprimé. Aucun chemin de code ne supprime un message qui n'existe pas ailleurs.
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
- **Vérifié en réel** : lecture, recherche, brouillon et archivage Gmail sur Gmail ; lecture et brouillon sur un
  serveur d'école. Le chemin d'archivage pour un serveur sans `MOVE` (copie puis retrait) n'est couvert que
  par des tests avec fausse connexion IMAP.
- **Recherche** : texte intégral (`TEXT`), floue chez Gmail ; pas de syntaxe de recherche propre à Gmail.
- **Fils de discussion** : reconstitués dans le dossier courant seulement.
- **Brouillons** : texte brut, sans pièce jointe. Pas d'envoi ni de suppression, par choix.
- **Noms de dossier** : ceux détectés par le serveur fonctionnent ; un nom saisi à la main avec des accents
  doit être donné dans l'encodage IMAP (UTF-7 modifié).
- **Pièces jointes** : non lues.

## Développement

```
uv run pytest
```

Ajouter un backend : implémenter `MailBackend` (et `DraftingBackend` / `ArchivingBackend` s'il écrit), puis
l'enregistrer dans `mail_mcp.registry.BACKENDS`.

## Licence

MIT, voir `LICENSE`.
