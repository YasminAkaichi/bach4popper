from dataclasses import dataclass


@dataclass
class Example:
    identifier: str
    positive: bool


@dataclass
class Fact:
    text: str
    example_identifier: str | None


@dataclass
class Rule:
    text: str


@dataclass
class Dataset:
    name: str

    positive_examples: list[Example]
    negative_examples: list[Example]

    facts: list[Fact]
    rules: list[Rule]

    bias: str