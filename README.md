# Charmed GitHub Jira Bot

Charmed version of https://github.com/canonical/gh-jira-sync-bot.

This is a [12-factor](https://documentation.ubuntu.com/charmcraft/stable/reference/extensions/fastapi-framework-extension/)
Kubernetes charm built with the `fastapi-framework` extension. The workload is the
`gh-jira-sync-bot` rock published from the application repository.

See https://charmhub.io/charmed-github-jira-bot for published channels.

## Deploy

```bash
juju deploy charmed-github-jira-bot
juju deploy redis-k8s --channel latest/edge --trust
juju integrate charmed-github-jira-bot redis-k8s
```

## Configure

Required configuration:

```bash
juju config charmed-github-jira-bot \
  jira-instance=https://<your>.atlassian.net \
  jira-username=<jira-username> \
  github-app-id=<github-app-id>
```

Secrets (GitHub private key, GitHub webhook secret, Jira API token) are passed as
[Juju user secrets](https://documentation.ubuntu.com/juju/en/latest/reference/secret/):

```bash
# GitHub App private key -> APP_GITHUB_PRIVATE_KEY
gh=$(juju add-secret gh-private-key private-key#file=./private-key.pem)
juju grant-secret gh-private-key charmed-github-jira-bot
juju config charmed-github-jira-bot github="$gh"

# GitHub webhook secret -> APP_WEBHOOK_SECRET
wh=$(juju add-secret gh-webhook secret=<webhook-secret>)
juju grant-secret gh-webhook charmed-github-jira-bot
juju config charmed-github-jira-bot webhook="$wh"

# Jira API token -> APP_JIRA_TOKEN
jira=$(juju add-secret jira-token token=<jira-token>)
juju grant-secret jira-token charmed-github-jira-bot
juju config charmed-github-jira-bot jira="$jira"
```

Optional configuration: `bot-name`, `max-concurrent-webhooks`, `default-bot-config`.

## Observability

Integrate with the Canonical Observability Stack:

```bash
juju integrate charmed-github-jira-bot prometheus
juju integrate charmed-github-jira-bot loki
juju integrate charmed-github-jira-bot grafana
```

## Ingress

```bash
juju deploy nginx-ingress-integrator --trust
juju integrate charmed-github-jira-bot nginx-ingress-integrator
```
