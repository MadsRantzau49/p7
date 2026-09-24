# Run local CI

```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh -o install-act.sh
sudo bash install-act.sh -b /usr/local/bin
act
```
Choose medium size

To run CI

```bash
act
```

To run specific job

```bash
act -j <name>
```

```bash
act -j backend
```
