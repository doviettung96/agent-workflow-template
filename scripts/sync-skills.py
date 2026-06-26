#!/usr/bin/env python3
"""Symlink template skills into projects, driven by each project's committed
.skills.config plus shared group defs in the template.

  group defs:   <template>/skill-groups.config      group <name> = <skill> ...
  per project:  <project>/.skills.config            tokens: group | skill | -group | -skill
  source:       <template>/skills/<name>/SKILL.md
  links (per agent dir present in the project):
      .claude/skills/<name>    -> <template>/skills/<name>           (dir)
      .harbor/skills/<name>    -> <template>/skills/<name>           (dir)
      .codex/skills/<name>.md  -> <template>/skills/<name>/SKILL.md  (file)

Usage:  sync-skills.py [PROJECT_DIR | PARENT_DIR] [--prune]
"""
import os, sys, shutil

HOME = os.path.expanduser("~")
TPL = os.environ.get("SKILLS_TEMPLATE_ROOT", os.path.join(HOME, "Projects/agentic-workflow-template"))
SKILLS = os.path.join(TPL, "skills")
GROUPS_FILE = os.path.join(TPL, "skill-groups.config")
AGENTS = ("claude", "codex", "harbor")


def load_groups():
    groups = {}
    if os.path.exists(GROUPS_FILE):
        for line in open(GROUPS_FILE):
            line = line.split("#", 1)[0].strip()
            if not line.startswith("group "):
                continue
            name, _, rest = line[len("group "):].partition("=")
            groups[name.strip()] = rest.split()
    return groups


def template_skills():
    return sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d)))


def resolve(conf, groups):
    tokens = []
    for line in open(conf):
        tokens += line.split("#", 1)[0].split()
    out = []
    expand = lambda t: groups.get(t, [t])
    for tok in tokens:
        if tok.startswith("-"):
            for s in expand(tok[1:]):
                if s in out:
                    out.remove(s)
        else:
            for s in expand(tok):
                if s not in out:
                    out.append(s)
    return out


def _rm(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.remove(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)


def materialize(proj, want, prune):
    ALL = template_skills()
    leftovers = []
    for ag in AGENTS:
        agdir = os.path.join(proj, "." + ag)
        if not os.path.isdir(agdir):
            continue
        sk = os.path.join(agdir, "skills")
        os.makedirs(sk, exist_ok=True)
        for t in ALL:                                    # refresh managed names
            _rm(os.path.join(sk, t)); _rm(os.path.join(sk, t + ".md"))
        for s in want:                                   # create links
            if ag == "codex":
                os.symlink(os.path.join(SKILLS, s, "SKILL.md"), os.path.join(sk, s + ".md"))
            else:
                os.symlink(os.path.join(SKILLS, s), os.path.join(sk, s))
        for e in sorted(os.listdir(sk)):                 # non-template leftovers
            base = e[:-3] if e.endswith(".md") else e
            if base not in ALL:
                if prune:
                    _rm(os.path.join(sk, e))
                else:
                    leftovers.append(".%s/skills/%s" % (ag, e))
    return leftovers


def do_project(proj, groups, prune):
    conf = os.path.join(proj, ".skills.config")
    if not os.path.exists(conf):
        return False
    want = resolve(conf, groups)
    print("project %-22s -> %s" % (os.path.basename(proj), " ".join(want)))
    for lo in materialize(proj, want, prune):
        print("    leftover %s" % lo)
    return True


def main():
    rest = [a for a in sys.argv[1:] if a != "--prune"]
    prune = "--prune" in sys.argv[1:]
    arg = rest[0] if rest else os.path.join(HOME, "Projects/tungace")
    if not os.path.isdir(SKILLS):
        sys.exit("no template skills: %s" % SKILLS)
    groups = load_groups()
    if os.path.exists(os.path.join(arg, ".skills.config")):
        do_project(arg, groups, prune)
    else:
        any_ = False
        for name in sorted(os.listdir(arg)):
            p = os.path.join(arg, name)
            if os.path.isdir(p) and do_project(p, groups, prune):
                any_ = True
        if not any_:
            print("no projects with .skills.config under %s" % arg)


if __name__ == "__main__":
    main()
