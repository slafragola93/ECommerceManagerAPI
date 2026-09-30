from src.services.email.renderer import render_template_string


def test_render_replaces_allowed_variables():
    html = render_template_string(
        "Ciao {{ firstname }}, ordine {{ reference }}",
        {"firstname": "Mario", "reference": "ABC"},
        ["firstname", "reference"],
    )
    assert "Mario" in html
    assert "ABC" in html


def test_render_unknown_variable_is_empty():
    html = render_template_string(
        "X{{ tracking }}Y",
        {"tracking": "should-not-appear", "firstname": "Mario"},
        ["firstname"],
    )
    assert "should-not-appear" not in html
    assert "XY" in html


def test_render_missing_value_is_empty():
    html = render_template_string("Hi {{ firstname }}!", {}, ["firstname"])
    assert html == "Hi !"
