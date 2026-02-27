# atx

A small CLI wrapper around `atmos terraform` and `atmos workflow` that:

- supports stack aliases (sb/prod/stage/etc.)
- offers a `fzf` stack picker when no stack is provided
- supports `-p/-a/-d/-c`, `-auto`, `-l/-list`, `-w`, `-s/--stack`
- forwards unknown args to `atmos` (component args + extras)

## Examples
```bash
atx -p sb eks/karpenter
atx -a -auto prod vpc
atx -d -auto -s stage rds
atx -c sb eks/cluster
atx -l
atx -w create-platform-cluster -f eks-cluster -s sb
```

## Shell completion

### Quick install (recommended)
This writes a completion script to `~/.config/atx/` and tells you what to source:

```bash
atx --install-completion bash
# or:
atx --install-completion zsh
atx --install-completion fish
```

## License

MIT. See [LICENSE](LICENSE).