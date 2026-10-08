# Run local CI

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh -o install-act.sh
sudo bash install-act.sh -b /usr/local/bin
act
```
Choose medium size

To run CI

```bash
act --secret-file .env
```

To run specific job

```bash
act -j <name> --secret-file .env
```

```bash
act -j backend --secret-file .env
```
