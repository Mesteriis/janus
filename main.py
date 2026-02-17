from pathlib import Path

from src.backend.cloudflare.client import CloudFlare
from src.backend.cloudflare import DnsException

print(CloudFlare.gen_token_url())

# 7m1g4Al1zhbKsQOunQp0b54Av6LQp5DkQm_0PxZN
token = "7m1g4Al1zhbKsQOunQp0b54Av6LQp5DkQm_0PxZN"
import asyncio


STATE_FILE = Path("./cloudflare.json").expanduser()


async def main():
    cf = CloudFlare(state_file=STATE_FILE)

    # 1. Пытаемся стартовать без вопросов
    if not await cf.bootstrap():
        print("\n❌ Cloudflare API token не найден или невалиден\n")
        print("👉 Открой ссылку и создай токен:")
        print(cf.gen_token_url())
        print()

        token = input("Вставь Cloudflare API token и нажми Enter:\n> ").strip()
        if not token:
            print("❌ Токен не введён, выходим")
            return

        await cf.set_token(token)
        print("\n✅ Токен сохранён\n")

    # 2. Клиент готов
    print("🚀 Cloudflare client READY\n")

    # 3. Пробуем реально что-то сделать
    result = await cf.provision_all_to_caddy(
        zone="domsub.me",
        dns_exceptions=[
            DnsException(
                fqdn="git.domsub.me",
                record_type="A",
                content="203.0.113.10",
            )
        ],
    )

    print("🎉 ГОТОВО")
    print("Tunnel name:", result["tunnel_name"])
    print("Tunnel id:", result["tunnel_id"])
    print("Zone:", result["zone"])


if __name__ == "__main__":
    asyncio.run(main())