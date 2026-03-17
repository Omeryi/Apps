import os
from typing import Optional, Tuple

from flask import Flask, Response, request
from google.cloud import datastore

app = Flask(__name__)
client = datastore.Client()

STATE_KIND = "State"
STATE_KEY = "global"
VAR_KIND = "Variable"
VALUE_COUNT_KIND = "ValueCount"
UNDO_KIND = "UndoNode"
REDO_KIND = "RedoNode"
HISTORY_KIND = "HistoryNode"


def text_response(body: str, status: int = 200) -> Response:
    return Response(body, status=status, mimetype="text/plain")


def get_required_name() -> Tuple[Optional[str], Optional[Response]]:
    name = request.args.get("name")
    if name is None or not name.strip():
        return None, text_response("Missing or invalid 'name' parameter", 400)
    return name.strip(), None


def get_required_value() -> Tuple[Optional[str], Optional[Response]]:
    value = request.args.get("value")
    if value is None:
        return None, text_response("Missing 'value' parameter", 400)
    return value, None


def state_key():
    return client.key(STATE_KIND, STATE_KEY)


def kind_key(kind: str, key_id):
    return client.key(kind, key_id)


def ensure_state(txn) -> datastore.Entity:
    state = client.get(state_key())
    if state is None:
        state = datastore.Entity(key=state_key())
        state.update(
            {
                "undo_top": None,
                "redo_top": None,
                "history_top": None,
                "next_undo_id": 1,
                "next_redo_id": 1,
                "next_history_id": 1,
                "redo_epoch": 0,
            }
        )
        client.put(state)
    return state


def ensure_state_exists() -> datastore.Entity:
    entity = client.get(state_key())
    if entity is not None:
        return entity
    entity = datastore.Entity(key=state_key())
    entity.update(
        {
            "undo_top": None,
            "redo_top": None,
            "history_top": None,
            "next_undo_id": 1,
            "next_redo_id": 1,
            "next_history_id": 1,
            "redo_epoch": 0,
        }
    )
    client.put(entity)
    return entity


def get_var(txn, name: str) -> Optional[str]:
    entity = client.get(kind_key(VAR_KIND, name))
    if entity is None:
        return None
    return entity.get("value")


def set_value_count(txn, value: str, delta: int) -> None:
    key = kind_key(VALUE_COUNT_KIND, value)
    entity = client.get(key)
    current = 0 if entity is None else int(entity.get("count", 0))
    new_count = current + delta
    if new_count <= 0:
        if entity is not None:
            client.delete(key)
        return
    if entity is None:
        entity = datastore.Entity(key=key)
    entity["count"] = new_count
    client.put(entity)


def set_variable(txn, name: str, new_value: Optional[str]) -> Optional[str]:
    key = kind_key(VAR_KIND, name)
    entity = client.get(key)
    old_value = None if entity is None else entity.get("value")

    if old_value == new_value:
        return old_value

    if old_value is not None:
        set_value_count(txn, old_value, -1)

    if new_value is None:
        if entity is not None:
            client.delete(key)
    else:
        if entity is None:
            entity = datastore.Entity(key=key)
        entity["value"] = new_value
        client.put(entity)
        set_value_count(txn, new_value, 1)

    return old_value


def push_undo(txn, state: datastore.Entity, name: str, before_value: Optional[str], after_value: Optional[str]) -> None:
    node_id = int(state["next_undo_id"])
    node = datastore.Entity(key=kind_key(UNDO_KIND, node_id))
    node.update(
        {
            "name": name,
            "before_value": before_value,
            "after_value": after_value,
            "prev_id": state.get("undo_top"),
        }
    )
    client.put(node)
    state["undo_top"] = node_id
    state["next_undo_id"] = node_id + 1


def push_redo(
    txn,
    state: datastore.Entity,
    name: str,
    before_value: Optional[str],
    after_value: Optional[str],
) -> None:
    node_id = int(state["next_redo_id"])
    node = datastore.Entity(key=kind_key(REDO_KIND, node_id))
    node.update(
        {
            "name": name,
            "before_value": before_value,
            "after_value": after_value,
            "prev_id": state.get("redo_top"),
            "epoch": state.get("redo_epoch", 0),
        }
    )
    client.put(node)
    state["redo_top"] = node_id
    state["next_redo_id"] = node_id + 1


def clear_redo(state: datastore.Entity) -> None:
    state["redo_top"] = None
    state["redo_epoch"] = int(state.get("redo_epoch", 0)) + 1


def push_history(txn, state: datastore.Entity, command: str, name: str, value: Optional[str]) -> None:
    node_id = int(state["next_history_id"])
    node = datastore.Entity(key=kind_key(HISTORY_KIND, node_id))
    node.update(
        {
            "command": command,
            "name": name,
            "value": value,
            "prev_id": state.get("history_top"),
        }
    )
    client.put(node)
    state["history_top"] = node_id
    state["next_history_id"] = node_id + 1


@app.route("/")
def index():
    return text_response("Key-Value Datastore Service")


@app.route("/set")
def set_command():
    name, name_err = get_required_name()
    if name_err:
        return name_err
    value, value_err = get_required_value()
    if value_err:
        return value_err

    with client.transaction() as txn:
        state = ensure_state(txn)
        old_value = set_variable(txn, name, value)
        push_undo(txn, state, name, old_value, value)
        clear_redo(state)
        push_history(txn, state, "SET", name, value)
        client.put(state)
    return text_response(f"{name} = {value}")


@app.route("/get")
def get_command():
    name, name_err = get_required_name()
    if name_err:
        return name_err

    ensure_state_exists()
    value_entity = client.get(kind_key(VAR_KIND, name))
    value = None if value_entity is None else value_entity.get("value")
    return text_response("None" if value is None else str(value))


@app.route("/unset")
def unset_command():
    name, name_err = get_required_name()
    if name_err:
        return name_err

    with client.transaction() as txn:
        state = ensure_state(txn)
        old_value = set_variable(txn, name, None)
        push_undo(txn, state, name, old_value, None)
        clear_redo(state)
        push_history(txn, state, "UNSET", name, None)
        client.put(state)
    return text_response(f"{name} = None")


@app.route("/numequalto")
def numequalto_command():
    value, value_err = get_required_value()
    if value_err:
        return value_err

    ensure_state_exists()
    entity = client.get(kind_key(VALUE_COUNT_KIND, value))
    count = 0 if entity is None else int(entity.get("count", 0))
    return text_response(str(count))


@app.route("/undo")
def undo_command():
    with client.transaction() as txn:
        state = ensure_state(txn)
        undo_top = state.get("undo_top")
        if undo_top is None:
            return text_response("NO COMMANDS")

        node = client.get(kind_key(UNDO_KIND, int(undo_top)))
        if node is None:
            state["undo_top"] = None
            client.put(state)
            return text_response("NO COMMANDS")

        name = node["name"]
        before_value = node.get("before_value")
        after_value = node.get("after_value")
        set_variable(txn, name, before_value)

        state["undo_top"] = node.get("prev_id")
        push_redo(txn, state, name, before_value, after_value)
        client.put(state)

    return text_response(f"{name} = {'None' if before_value is None else before_value}")


@app.route("/redo")
def redo_command():
    with client.transaction() as txn:
        state = ensure_state(txn)
        redo_top = state.get("redo_top")
        if redo_top is None:
            return text_response("NO COMMANDS")

        node = client.get(kind_key(REDO_KIND, int(redo_top)))
        if node is None:
            state["redo_top"] = None
            client.put(state)
            return text_response("NO COMMANDS")

        if int(node.get("epoch", -1)) != int(state.get("redo_epoch", 0)):
            state["redo_top"] = None
            client.put(state)
            return text_response("NO COMMANDS")

        name = node["name"]
        before_value = node.get("before_value")
        after_value = node.get("after_value")
        set_variable(txn, name, after_value)

        state["redo_top"] = node.get("prev_id")
        push_undo(txn, state, name, before_value, after_value)
        client.put(state)

    return text_response(f"{name} = {'None' if after_value is None else after_value}")


@app.route("/history")
def history_command():
    limit_raw = request.args.get("limit", "20")
    try:
        limit = max(1, min(100, int(limit_raw)))
    except ValueError:
        return text_response("Invalid 'limit' parameter", 400)

    lines = []
    state = ensure_state_exists()
    current_id = state.get("history_top")
    while current_id is not None and len(lines) < limit:
        node = client.get(kind_key(HISTORY_KIND, int(current_id)))
        if node is None:
            break
        cmd = node.get("command")
        name = node.get("name")
        value = node.get("value")
        if cmd == "SET":
            lines.append(f"SET {name} {value}")
        elif cmd == "UNSET":
            lines.append(f"UNSET {name}")
        current_id = node.get("prev_id")

    if not lines:
        return text_response("NO HISTORY")
    return text_response("\n".join(reversed(lines)))


@app.route("/end")
def end_command():
    keys_to_delete = []
    for kind in (VAR_KIND, VALUE_COUNT_KIND, UNDO_KIND, REDO_KIND, HISTORY_KIND, STATE_KIND):
        query = client.query(kind=kind)
        query.keys_only()
        for entity in query.fetch():
            keys_to_delete.append(entity.key)

    batch_size = 500
    for i in range(0, len(keys_to_delete), batch_size):
        client.delete_multi(keys_to_delete[i : i + batch_size])

    with client.transaction() as txn:
        ensure_state(txn)

    return text_response("CLEANED")


@app.errorhandler(500)
def internal_error(_err):
    return text_response("Internal server error", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
