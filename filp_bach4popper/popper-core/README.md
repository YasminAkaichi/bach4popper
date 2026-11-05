# popper-core

Popper 1.1.0 (https://github.com/logic-and-learning-lab/Popper), bundled so that
Bach4Popper runs without any other installation. Changes with respect to the
original:

* `loop.py`: `build_rules_server` (clause-level feedback built from the answers
  of the clients) and the pieces of `build_rules` it shares;
* `federatedtester.py`: `FederatedTester`, used by the server; it loads only the
  logic of `lp/test.pl` (no examples, no background knowledge), because the
  server owns no data and only needs the syntactic redundancy checks;
* `tester.py`, `federatedtester.py`, `asp.py`: `pkg_resources` replaced by
  `pathlib` (`pkg_resources` is no longer shipped with recent Python versions).
