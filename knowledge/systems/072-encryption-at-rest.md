# 72. Encryption at Rest

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)encrypt|decrypt|\bkms\b|fernet|\baes\b|keychain|cert\.pem`

## What it is
Encryption at rest means stored data (disks, volumes, databases, backups, files) is unreadable without a key. Its threat model is narrow and important: it protects against someone getting the storage while the system is not unlocked, such as a stolen laptop, a removed drive, a discarded disk or a copied backup. It does **not** protect against anything running on the unlocked system. The app, the logged-in user and any malware in that session read plaintext as normal, and access control has to cover that.

It comes at several layers: full disk (FileVault, BitLocker, LUKS), volume or file, database (TDE), and application-level (field encryption). Keys must live apart from the data: envelope encryption wraps data keys with a key-encryption key kept in a key store or a hardware module. The cheapest protection is not storing sensitive data at all.

## When it is worth it
Full-disk encryption on every laptop and server, and encryption on every backup and cloud volume, is table stakes and usually free: one setting. Application-level or field-level encryption is worth it only when the threat is someone with database or storage access who should not read specific fields (shared databases, regulated data, multi-tenant systems). Doing it for data that only one process reads, on an encrypted disk, adds key-management risk for little gain.

## How it fails
- **Unencrypted laptop or drive:** the machine is lost or stolen → every secret, token and log on it is readable offline.
- **Unencrypted backups:** the primary disk is encrypted but its backup is not → the backup leaks it all.
- **Key next to the data:** the decryption key is in the same database, bucket or config file → one breach yields both.
- **Mistaking at-rest for runtime protection:** "it's encrypted" while the attacker is already inside the running system → no protection at all.
- **Keeping what you do not need:** old logs, IPs and payloads kept forever → more to leak, with no use.

## Review checklist
- [ ] **Is new persistent storage encrypted at rest?** · Applies when: the diff adds a database, volume, bucket, backup target or long-lived disk. · Block if: encryption at rest is not enabled for it, or not inherited from an encrypted host disk.
- [ ] **Is the key stored apart from the data?** · Applies when: the diff adds application-level encryption or a key for it. · Block if: the key lives in the same store, file or repository as the encrypted data, or is hard-coded.
- [ ] **Is the encryption authenticated and from a vetted library?** · Applies when: the diff encrypts data itself. · Block if: it uses ECB, unauthenticated CBC or CTR without a MAC, a hand-rolled cipher, or a non-random IV or nonce.
- [ ] **Is the data needed at all?** · Applies when: the diff starts storing secrets, personal data (IPs, emails) or full payloads. · Block if: there is no stated use for it, or no retention limit.

## In the factory
- `fdesetup status` reports `FileVault is On`. On Apple silicon the internal disk is always hardware-encrypted, and FileVault adds the login password to the key. So everything the factory keeps on this Mac is encrypted at rest: `.env` (mode 600), `.factory-logs` (4.1 MB), run workdirs, and Colima's VM disk (`~/.colima`, 25 GB). Right.
- The `gh` token is in the macOS keychain, not a file. Right.
- GitHub stores the repo, Actions secrets (sealed with libsodium) and artifacts. That is provider-managed encryption at rest.
- What this does not cover: anything running as the user, or inside the Colima VM, which mounts the home folder, reads all of it in plaintext. That is why the VM-reachability gap in 080-ssrf.md and the push-scan gap in 067-secrets-management.md matter.
- Noted for 084-backups.md: Time Machine has no destination configured (`tmutil: No destinations configured`), so there is no backup to encrypt, or to restore.
- Not applicable at today's load: application-level or field encryption. One process reads its own files on an encrypted disk.

## Proof
Two macOS disk images built from the same folder holding a fake secret, one plain and one AES-256 (`hdiutil create -format UDRW ... [-encryption AES-256 -stdinpass]`). The raw image files were then searched, and the encrypted one was mounted:
```
A  unencrypted image on disk: secret found in raw bytes = yes
A  AES-256 image on disk:     secret found in raw bytes = no
B  once unlocked and mounted, any process of this user reads: FAKE-SECRET-at-rest-4c1d7e
B  after detach, readable = no
```
Both images were deleted afterwards.

## Related
073-encryption-in-transit.md, 067-secrets-management.md, 084-backups.md, 080-ssrf.md, 059-logging.md

## Sources
- "Cryptographic Storage Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- "Volume encryption with FileVault in macOS", Apple Platform Security Guide: https://support.apple.com/guide/security/volume-encryption-with-filevault-sec4c6dc1b6e/web
