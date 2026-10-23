"""Komut satırı araçları: `python -m app.cli sifre-olustur`."""
import getpass
import sys

from app.admin import BCRYPT_EN_COK_BAYT, sifre_hashle


def sifre_olustur() -> int:
    sifre = getpass.getpass("Yeni yönetici şifresi: ")
    if not sifre:
        print("Şifre boş olamaz.", file=sys.stderr)
        return 1
    if len(sifre.encode()) > BCRYPT_EN_COK_BAYT:
        print(f"Şifre en fazla {BCRYPT_EN_COK_BAYT} bayt olabilir.", file=sys.stderr)
        return 1
    if getpass.getpass("Şifre (tekrar): ") != sifre:
        print("Şifreler uyuşmuyor.", file=sys.stderr)
        return 1
    hash_ = sifre_hashle(sifre)
    print("\n.env dosyasına şu satırı ekleyin:\n")
    print(f"ADMIN_SIFRE_HASH={hash_}")
    print(
        "\nDocker Compose, .env içindeki '$' işaretini değişken sayar; compose ile "
        "kullanacaksanız (pydantic-settings $$ değerini olduğu gibi okur, bu yüzden yalnızca compose için) her '$' yerine '$$' yazın:\n"
    )
    print(f"ADMIN_SIFRE_HASH={hash_.replace('$', '$$')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["sifre-olustur"]:
        return sifre_olustur()
    print("Kullanım: python -m app.cli sifre-olustur", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
