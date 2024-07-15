from src import get_db
from src.main import app
from src.models import Message
from src.services.auth import get_current_user
from ..utils import client, test_message, override_get_db, override_get_current_user, TestingSessionLocal, \
    override_get_current_user_read_only

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

expected_results = [
    {
        "id_message": 5,
        "id_user": 1,
        "message": "Admiration stimulated cultivated reasonable be projection possession of. Real no near room ye bred sake if some. Is arranging furnished knowledge. t27CnFwQbbK0uSn1w8iNFrLldmdV2RmXnflQ",
    },
    {
        "id_message": 4,
        "id_user": 1,
        "message": "Started his hearted any civilly. So me by marianne admitted speaking. Men bred fine call ask. Cease one miles truth day above seven. lCG5XSxlDzXaJf6gIOGD4htTn2FV5I8bCQdYBlQb3Z9nJAp1xS7KdZC9xhUHXL",
    },
    {
        "id_message": 3,
        "id_user": None,
        "message": "Carriage quitting securing be appetite it declared. High eyes kept so busy feel call in. Would day nor ask walls known. But preserved advantage. 8G4rAsZmzgDV0sDJYwzrBrhXEFXsi1ZtNDbU5GgxD5rj2uHcXV0Dg54AAX9WpnNFUya8IM3EowysKvX",
    },
    {
        "id_message": 2,
        "id_user": None,
        "message": "Sense child do state to defer mr of forty. Become latter but nor abroad wisdom waited. Was delivered gentleman acuteness but daughters. MCBRPh0Vx0tK6aQD6hhKkEOPxsVZ4O4CWIbI0Wl1MhKJA8RKu1RdmG1VQJr",
    },
    {
        "id_message": 1,
        "id_user": 1,
        "message": "Necessary breakfast he attention expenses resolution. Outward general passage another as it. Very his are come man walk one next. mN8dM T72cEAfKWGeiA2j4cKpJBClC66m0M0D0fBc7GAZdQqjfZuiDM0K8LwZ3kSd",
    }
]


def test_get_messages(test_message):
    response = client.get("/api/v1/message/")

    assert response.status_code == 200
    assert response.json()["messages"] == expected_results
    assert response.json()["total"] == 5


def test_get_message_by_id(test_message):
    response = client.get('/api/v1/message/2')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json() == expected_results[3]

    response = client.get('/api/v1/message/10')
    assert response.status_code == 404


def test_get_message_by_user(test_message):
    response = client.get('/api/v1/message/?user_id=1')

    # Verifica della risposta
    assert response.status_code == 200

    assert response.json()["messages"] == [expected_results[0], expected_results[1], expected_results[4]]

    response = client.get('/api/v1/message/10')
    assert response.status_code == 404


def test_create_message(test_message):
    request_body = {
        "message": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent ultricies mi eu mollis placerat. Sed quis felis ex. Pellentesque mi erat, porttitor non commodo eu, pretium quis purus. Vivamus pharetra arcu in elit tempus, vel sodales risus pharetra. In luctus ultrices mi, et facilisis neque placerat nec. Proin et tempor est. Donec vitae eros posuere, dapibus urna quis, pharetra enim. Proin tellus lorem, fringilla eget luctus vitae, semper non odio. Etiam eu purus rutrum, posuere leo in, condimentum tellus. Praesent orci velit, rhoncus quis metus eget, congue tristique nisl. Ut viverra finibus magna sit amet maximus. Vivamus dapibus, metus in aliquet consequat, lorem massa elementum risus, in venenatis risus augue ac mi.Donec vitae lacus nec leo ornare lobortis. Vivamus sem elit, dapibus sit amet rhoncus eget, hendrerit in ipsum. Donec condimentum velit felis. Donec nisl orci, bibendum ut pulvinar non, maximus a dui. Donec eleifend nulla in urna feugiat, id iaculis neque ullamcorper. Nunc nec turpis orci. Suspendisse eleifend nulla nec orci imperdiet, et scelerisque justo hendrerit. Donec commodo gravida diam nec convallis. Phasellus ex lectus, blandit eu commodo et, rhoncus eu erat. Proin in luctus arcu. Cras orci erat, ultricies nec nisl quis, facilisis consectetur augue. Proin pulvinar convallis suscipit. In vehicula, diam eleifend dapibus porttitor, augue dolor consequat erat, eget finibus tortor mauris et diam. Donec accumsan turpis erat, vel maximus ex consequat sit amet.In porta a lacus ut rhoncus. Nam egestas diam a turpis faucibus, ac feugiat lectus pharetra. Nulla consequat nisl ut neque rutrum sagittis. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Vestibulum hendrerit accumsan velit, a pharetra elit pellentesque eget. Sed sit amet ex ligula. Sed risus mauris, interdum nec vestibulum vel, mollis eu elit.Suspendisse mollis dignissim felis id efficitur. Ut volutpat felis eget sollicitudin euismod. Vivamus bibendum lorem at cursus dictum. Nulla facilisi. Donec vel elit ac ex ultrices viverra ac id turpis. Proin ac molestie justo, non euismod arcu. Vestibulum at hendrerit lacus. Vivamus accumsan tempus metus, vel pellentesque tellus sodales sit amet. Nam ut ipsum sit amet dui facilisis ultricies nec vitae neque. Suspendisse potenti.Curabitur rutrum lobortis nulla, vestibulum placerat neque consequat id. Vestibulum id dapibus ante. Aenean sollicitudin purus in orci tincidunt venenatis. In dui ipsum, laoreet id nisi eget, efficitur pharetra magna. Praesent non mollis lacus, sed posuere risus. Sed ut commodo ligula, et efficitur orci. Nullam blandit eros a tortor pulvinar, id fringilla urna sagittis. Morbi eu nibh scelerisque, tristique justo vel, congue tortor. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Integer semper risus sit amet ipsum ultricies, porttitor finibus leo cursus. Quisque eu tortor odio. Pellentesque fermentum quam tellus, id varius mauris feugiat vitae. Vivamus id purus neque. "
    }

    response = client.post("/api/v1/message/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    message = db.query(Message).filter(Message.id_message == 6).first()
    assert message is not None
    assert message.id_user == None
    assert message.message == request_body.get('message')

    request_body = {
        "message": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent ultricies mi eu mollis placerat. Sed quis felis ex. Pellentesque mi erat, porttitor non commodo eu, pretium quis purus. Vivamus pharetra arcu in elit tempus, vel sodales risus pharetra. In luctus ultrices mi, et facilisis neque placerat nec. Proin et tempor est. Donec vitae eros posuere, dapibus urna quis, pharetra enim. Proin tellus lorem, fringilla eget luctus vitae, semper non odio. Etiam eu purus rutrum, posuere leo in, condimentum tellus. Praesent orci velit, rhoncus quis metus eget, congue tristique nisl. Ut viverra finibus magna sit amet maximus. Vivamus dapibus, metus in aliquet consequat, lorem massa elementum risus, in venenatis risus augue ac mi.Donec vitae lacus nec leo ornare lobortis. Vivamus sem elit, dapibus sit amet rhoncus eget, hendrerit in ipsum. Donec condimentum velit felis. Donec nisl orci, bibendum ut pulvinar non, maximus a dui. Donec eleifend nulla in urna feugiat, id iaculis neque ullamcorper. Nunc nec turpis orci. Suspendisse eleifend nulla nec orci imperdiet, et scelerisque justo hendrerit. Donec commodo gravida diam nec convallis. Phasellus ex lectus, blandit eu commodo et, rhoncus eu erat. Proin in luctus arcu. Cras orci erat, ultricies nec nisl quis, facilisis consectetur augue. Proin pulvinar convallis suscipit. In vehicula, diam eleifend dapibus porttitor, augue dolor consequat erat, eget finibus tortor mauris et diam. Donec accumsan turpis erat, vel maximus ex consequat sit amet.In porta a lacus ut rhoncus. Nam egestas diam a turpis faucibus, ac feugiat lectus pharetra. Nulla consequat nisl ut neque rutrum sagittis. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Vestibulum hendrerit accumsan velit, a pharetra elit pellentesque eget. Sed sit amet ex ligula. Sed risus mauris, interdum nec vestibulum vel, mollis eu elit.Suspendisse mollis dignissim felis id efficitur. Ut volutpat felis eget sollicitudin euismod. Vivamus bibendum lorem at cursus dictum. Nulla facilisi. Donec vel elit ac ex ultrices viverra ac id turpis. Proin ac molestie justo, non euismod arcu. Vestibulum at hendrerit lacus. Vivamus accumsan tempus metus, vel pellentesque tellus sodales sit amet. Nam ut ipsum sit amet dui facilisis ultricies nec vitae neque. Suspendisse potenti.Curabitur rutrum lobortis nulla, vestibulum placerat neque consequat id. Vestibulum id dapibus ante. Aenean sollicitudin purus in orci tincidunt venenatis. In dui ipsum, laoreet id nisi eget, efficitur pharetra magna. Praesent non mollis lacus, sed posuere risus. Sed ut commodo ligula, et efficitur orci. Nullam blandit eros a tortor pulvinar, id fringilla urna sagittis. Morbi eu nibh scelerisque, tristique justo vel, congue tortor. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Integer semper risus sit amet ipsum ultricies, porttitor finibus leo cursus. Quisque eu tortor odio. Pellentesque fermentum quam tellus, id varius mauris feugiat vitae. Vivamus id purus neque. "
    }

    response = client.post("/api/v1/message/?relate_to_user=true", json=request_body)

    # Verifica della risposta
    assert response.status_code == 201

    db = TestingSessionLocal()

    message = db.query(Message).filter(Message.id_message == 7).first()
    assert message is not None
    assert message.id_user == 1
    assert message.message == request_body.get('message')


def test_delete_message(test_message):
    # not found
    response = client.delete('/api/v1/message/200')
    assert response.status_code == 404

    response = client.delete("/api/v1/message/2")

    # Verifica della risposta
    assert response.status_code == 204


def test_update_message(test_message):
    request_body = {
        "message": "Messaggio di default"
    }
    response = client.put("/api/v1/message/1", json=request_body)
    assert response.status_code == 200

    db = TestingSessionLocal()

    message = db.query(Message).filter(Message.id_message == 1).first()
    assert message is not None

    assert message.message == request_body.get('message')

# TEST CON PERMESSI USER


def test_get_messages_with_user_permissions(test_message):
    app.dependency_overrides[get_current_user] = override_get_current_user_read_only
    response = client.get("/api/v1/message/")

    assert response.status_code == 403


def test_get_message_by_id_with_user_permissions(test_message):
    response = client.get('/api/v1/message/2')

    # Verifica della risposta
    assert response.status_code == 403


def test_get_message_by_user_with_user_permissions(test_message):
    response = client.get('/api/v1/message/?user_id=1')

    # Verifica della risposta
    assert response.status_code == 403


def test_create_message_with_user_permissions(test_message):
    request_body = {
        "message": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent ultricies mi eu mollis placerat. Sed quis felis ex. Pellentesque mi erat, porttitor non commodo eu, pretium quis purus. Vivamus pharetra arcu in elit tempus, vel sodales risus pharetra. In luctus ultrices mi, et facilisis neque placerat nec. Proin et tempor est. Donec vitae eros posuere, dapibus urna quis, pharetra enim. Proin tellus lorem, fringilla eget luctus vitae, semper non odio. Etiam eu purus rutrum, posuere leo in, condimentum tellus. Praesent orci velit, rhoncus quis metus eget, congue tristique nisl. Ut viverra finibus magna sit amet maximus. Vivamus dapibus, metus in aliquet consequat, lorem massa elementum risus, in venenatis risus augue ac mi.Donec vitae lacus nec leo ornare lobortis. Vivamus sem elit, dapibus sit amet rhoncus eget, hendrerit in ipsum. Donec condimentum velit felis. Donec nisl orci, bibendum ut pulvinar non, maximus a dui. Donec eleifend nulla in urna feugiat, id iaculis neque ullamcorper. Nunc nec turpis orci. Suspendisse eleifend nulla nec orci imperdiet, et scelerisque justo hendrerit. Donec commodo gravida diam nec convallis. Phasellus ex lectus, blandit eu commodo et, rhoncus eu erat. Proin in luctus arcu. Cras orci erat, ultricies nec nisl quis, facilisis consectetur augue. Proin pulvinar convallis suscipit. In vehicula, diam eleifend dapibus porttitor, augue dolor consequat erat, eget finibus tortor mauris et diam. Donec accumsan turpis erat, vel maximus ex consequat sit amet.In porta a lacus ut rhoncus. Nam egestas diam a turpis faucibus, ac feugiat lectus pharetra. Nulla consequat nisl ut neque rutrum sagittis. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Vestibulum hendrerit accumsan velit, a pharetra elit pellentesque eget. Sed sit amet ex ligula. Sed risus mauris, interdum nec vestibulum vel, mollis eu elit.Suspendisse mollis dignissim felis id efficitur. Ut volutpat felis eget sollicitudin euismod. Vivamus bibendum lorem at cursus dictum. Nulla facilisi. Donec vel elit ac ex ultrices viverra ac id turpis. Proin ac molestie justo, non euismod arcu. Vestibulum at hendrerit lacus. Vivamus accumsan tempus metus, vel pellentesque tellus sodales sit amet. Nam ut ipsum sit amet dui facilisis ultricies nec vitae neque. Suspendisse potenti.Curabitur rutrum lobortis nulla, vestibulum placerat neque consequat id. Vestibulum id dapibus ante. Aenean sollicitudin purus in orci tincidunt venenatis. In dui ipsum, laoreet id nisi eget, efficitur pharetra magna. Praesent non mollis lacus, sed posuere risus. Sed ut commodo ligula, et efficitur orci. Nullam blandit eros a tortor pulvinar, id fringilla urna sagittis. Morbi eu nibh scelerisque, tristique justo vel, congue tortor. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Integer semper risus sit amet ipsum ultricies, porttitor finibus leo cursus. Quisque eu tortor odio. Pellentesque fermentum quam tellus, id varius mauris feugiat vitae. Vivamus id purus neque. "
    }

    response = client.post("/api/v1/message/", json=request_body)

    # Verifica della risposta
    assert response.status_code == 403


def test_delete_message_with_user_permissions(test_message):
    response = client.delete('/api/v1/message/200')
    assert response.status_code == 403


def test_update_message_with_user_permissions(test_message):
    request_body = {
        "message": "Messaggio di default"
    }
    response = client.put("/api/v1/message/1", json=request_body)
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = override_get_current_user
