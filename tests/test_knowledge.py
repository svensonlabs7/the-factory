import pathlib
import re

SYSTEMS = pathlib.Path(__file__).resolve().parents[1] / "knowledge" / "systems"
ROW = re.compile(r"^\| (\d+) \| (.+?) \| (todo|learned|proven) \|\s*(.*?)\s*\|$")


def rows():
    return [m.groups() for line in (SYSTEMS / "LEDGER.md").read_text().splitlines() if (m := ROW.match(line))]


def test_ledger_has_each_of_the_111_topics_once():
    numbers = sorted(int(number) for number, *_ in rows())
    assert numbers == list(range(1, 112))


def test_every_finished_topic_links_a_card_that_exists():
    for number, topic, status, card in rows():
        if status == "todo":
            continue
        link = re.fullmatch(r"\[(.+?)\]\((.+?)\)", card)
        assert link, f"{number} {topic} is {status} but links no card"
        assert (SYSTEMS / link.group(2)).is_file(), f"{number} {topic} links a missing card {link.group(2)}"
