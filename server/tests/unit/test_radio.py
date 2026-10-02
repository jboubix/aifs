from atc_server.radio import RadioDirectory


def test_listeners_match_on_kilohertz():
    radio = RadioDirectory()
    radio.tune("a", 121.9)
    radio.tune("b", 121.9004)
    radio.tune("c", 118.1)
    assert radio.listeners(121.9001) == ["a", "b"]
    radio.drop("a")
    assert radio.listeners(121.9) == ["b"]
