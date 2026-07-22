from src.models import Action, KeyBinding, Match, Profile, Settings, Config


def test_models_construct_and_default():
    a = Action(type="send_keys", keys="ctrl+c")
    b = KeyBinding(label="Copy", action=a)
    p = Profile(name="Default", color="#2d2d2d", match=Match(process=["*"]), keys={"k1": b})
    s = Settings()
    c = Config(settings=s, controls={"k1": "f13"}, profiles=[p])

    assert c.profiles[0].keys["k1"].action.keys == "ctrl+c"
    assert c.controls["k1"] == "f13"
    assert s.hud_mode == "flash"           # default
    assert p.match.title is None           # default
    assert Match().process == []           # default is a fresh list
