#!/usr/bin/env python3

import json
import os
import pathlib
import re
import subprocess
from argparse import ArgumentParser

rex = re.compile(r'version = (\S+)')


def regex_matches(relpath, regex=rex):
    p = pathlib.Path(relpath)
    assert p.exists()
    for line in open(str(p)):
        m = regex.match(line)
        if m is not None:
            return m


def read_toml_version(relpath):
    res = regex_matches(relpath, rex)
    if res is not None:
        return res.group(1)
    raise ValueError(f"no version found in {relpath}")


def replace_toml_version(relpath, newversion):
    p = pathlib.Path(relpath)
    assert p.exists()
    tmp_path = str(p) + "_tmp"
    with open(tmp_path, "w") as f:
        for line in open(str(p)):
            m = rex.match(line)
            if m is not None:
                print(f"{relpath}: set version={newversion}")
                f.write(f'version = {newversion}\n')
            else:
                f.write(line)
    os.rename(tmp_path, str(p))


def read_json_version(relpath):
    p = pathlib.Path(relpath)
    assert p.exists()
    with open(p) as f:
        json_data = json.loads(f.read())
    return json_data["version"]


def update_package_json(relpath, newversion):
    p = pathlib.Path(relpath)
    assert p.exists()
    with open(p) as f:
        json_data = json.loads(f.read())
    json_data["version"] = newversion
    with open(p, "w") as f:
        f.write(json.dumps(json_data, sort_keys=True, indent=2))


def main():
    parser = ArgumentParser(prog="set_core_version")
    parser.add_argument("newversion")

    toml_list = [
        "setup.cfg",
    ]
    try:
        opts = parser.parse_args()
    except SystemExit:
        print()
        for x in toml_list:
            print(f"{x}: {read_toml_version(x)}")
        print()
        raise SystemExit("need argument: new version, example: 1.25.0")

    newversion = opts.newversion
    if newversion.count(".") < 2:
        raise SystemExit("need at least two dots in version")

    print(read_toml_version("setup.cfg"))

    if "alpha" not in newversion:
        for line in open("CHANGELOG.rst"):
            if line.startswith(newversion):
                break
        else:
            raise SystemExit(
                f"CHANGELOG.rst contains no entry for version: {newversion}"
            )

    for toml_filename in toml_list:
        replace_toml_version(toml_filename, newversion)

    print("adding changes to git index")
    if not os.environ.get("MAILCOW_TOKEN"):
        print()
        choice = input("no MAILCOW_TOKEN environment variable, do you want to skip CI? [Y/n] ")
        if choice.lower() == "n":
            print()
            raise SystemExit("Please provide a MAILCOW_TOKEN environment variable to run CI")
    else:
        subprocess.call(["tox"])
    subprocess.call(["git", "add", "-u"])
    print()
    print("showing changes:")
    print()
    subprocess.call(["git", "diff", "--staged"])
    print()
    choice = input(f"commit these changes as 'new {newversion} release', tag it, and push it? [Y/n] ")
    if choice.lower() == "n":
        print()
        print(f"you can commit the changes yourself with: git commit -m 'new {newversion} release'")
        print("after commit, on master make sure to: ")
        print()
        print(f"   git tag -a {newversion}")
        print(f"   git push origin {newversion}")
        print()
    else:
        subprocess.call(["git", "commit", "-m", f"'new {newversion} release'"])
        subprocess.call(["git", "tag", "-a", f"{newversion}"])
        subprocess.call(["git", "push", "origin", f"{newversion}"])


if __name__ == "__main__":
    main()
