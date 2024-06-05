import keyring
import questionary


def _get_password(system, key, **kwargs):
    store_keys = kwargs["modify"][0]
    update_keys = kwargs["modify"][1]
    password = keyring.get_password(system, key)
    if update_keys or password is None:
        password = questionary.password(f"Enter the {system} {key}: ").ask()
    if store_keys:
        if password is not None:
            try:
                keyring.set_password(system, key, password)
            except keyring.errors.PasswordSetError:
                print("Failed to store password")

    return password
