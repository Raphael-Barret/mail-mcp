# mail-mcp

Serveur [MCP](https://modelcontextprotocol.io) local qui donne à un assistant (Claude Code, par exemple)
un accès à plusieurs boîtes mail, **en lecture seule par défaut**.

- Plusieurs comptes, un format de sortie unique (compte, id, expéditeur, sujet, date, non lu, extrait).
- Les secrets restent dans le Trousseau macOS, jamais dans un fichier ni dans le dépôt.
- Les écritures (brouillon, archivage) sont des capacités distinctes, désactivées par défaut,
  activées compte par compte dans la configuration, jamais par un argument d'outil.
- Le contenu des mails est traité comme une donnée non fiable, et chaque sortie d'outil le signale.

État actuel : backend IMAP (Gmail, tout serveur IMAP classique). Prévus : Gmail API, Microsoft Graph.

## Installation

Prérequis : macOS (Trousseau), [uv](https://docs.astral.sh/uv/), Python 3.11 ou plus.

```
git clone <url-du-depot> mail-mcp
cd mail-mcp
uv sync
uv run pytest
```

## Configuration

1. Copier `config.example.toml` vers `~/.config/mail-mcp/config.toml` (ou définir `MAIL_MCP_CONFIG`)
   et décrire vos comptes. Une entrée `[accounts.<nom>]` suffit pour ajouter un compte.
2. Ranger le mot de passe de chaque compte dans le Trousseau, **dans un vrai terminal** (pas en argument,
   pour qu'il ne finisse pas dans l'historique du shell), avec le nom du compte comme identifiant :

   ```
   security add-generic-password -s mail-mcp -a <nom-du-compte> -w
   ```

   Si macOS répond « User interaction is not allowed », déverrouiller d'abord le Trousseau :
   `security unlock-keychain ~/Library/Keychains/login.keychain-db`.
3. Redémarrer le serveur après chaque changement de configuration (elle est lue au démarrage).

### Gmail

Activer la validation en deux étapes, puis créer un **mot de passe d'application** sur
<https://myaccount.google.com/apppasswords>. C'est lui qu'on range dans le Trousseau. Hôte `imap.gmail.com`,
port 993, `security = "ssl"`. Chez Gmail, archiver retire le message du dossier INBOX : il reste dans
« Tous les messages » (vérifié avant de le retirer).

### Autre serveur IMAP (école, entreprise)

Les paramètres sont souvent publiés dans un fichier d'autoconfiguration :
`https://autoconfig.<domaine>/mail/config-v1.1.xml` (hôte, port, sécurité, forme de l'identifiant).
Sinon, les lire dans les réglages du compte de votre client mail. Pour archiver sur un serveur sans dossier
d'archive reconnu, créer le dossier dans votre client et le nommer dans `archive_folder`.

## Enregistrement dans Claude Code

```
claude mcp add --scope user mail -- uv run --directory /chemin/vers/mail-mcp mail-mcp
```

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
  autre message du dossier est déjà marqué supprimé. Un message n'est jamais détruit.
- **Brouillon, jamais envoi.** Un brouillon part dans le dossier Brouillons ; c'est vous qui l'envoyez.
  Les adresses et l'objet sont refusés s'ils contiennent un saut de ligne (injection d'en-têtes).
- **Contenu non fiable.** Un mail peut contenir des instructions à l'intention de l'assistant. Les sorties de
  lecture sont enveloppées dans un avertissement, mais la défense reste côté usage : ne pas mettre les outils
  d'écriture en autorisation automatique, relire les brouillons.
- **Les identifiants ne sont pas limités.** Un mot de passe d'application ou un mot de passe de compte donne
  tous les droits côté serveur. La lecture seule ne tient que par ce code et votre configuration.

## Développement

```
uv run pytest
```

Ajouter un backend : implémenter `MailBackend` (et `DraftingBackend` / `ArchivingBackend` s'il écrit), puis
l'enregistrer dans `mail_mcp.registry.BACKENDS`.

## Licence

MIT, voir `LICENSE`.
