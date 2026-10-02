# LastZHood — .env Kurulum Notları

Repo: https://github.com/Dostarki/fixlilastzhood — `/app` içine kuruldu ve preview'da çalışıyor.

## Backend (`/app/backend/.env`)
Çalışması için TÜM değişkenler dolduruldu. Aşağıdakiler **dev/placeholder** değerlerdir — deploy öncesi
GERÇEK değerlerle değiştirilmeli:

| Değişken | Durum | Açıklama |
|---|---|---|
| `TREASURY_ADDRESS` | PLACEHOLDER (`0x...dEaD`) | ETH ödemelerinin gideceği gerçek hazine (treasury) cüzdan adresin |
| `ADMIN_PASSWORD_HASH` | DEV (`admin123` bcrypt) | Operatör admin paneli şifresi. Kendi şifrenin bcrypt hash'i ile değiştir |
| `JWT_SECRET` | DEV (rastgele) | İstersen kendi secret'ınla değiştir |
| `EARLY_ADMIN_PASSWORD` | DEV (`changeme_early_admin`) | Early/registry admin şifresi |
| `EARLY_JWT_SECRET` | DEV (rastgele) | Early modül JWT secret |
| `X_*_LINK` / `X_*_TEXT` | PLACEHOLDER | X (Twitter) kampanya linkleri/metinleri — gerçek hesabınla güncelle |

Çalışan gerçek değerler (dokunmana gerek yok):
- `ROBINHOOD_CHAIN_ID=4663`, `ROBINHOOD_RPC_URL=https://rpc.mainnet.chain.robinhood.com`
- `COINBASE_SPOT_URL` (ETH/USD fiyat), `MONGO_URL/DB_NAME` (platform tarafından yönetilir)

## Frontend (`/app/frontend/.env`)
| Değişken | Durum | Açıklama |
|---|---|---|
| `REACT_APP_WALLETCONNECT_PROJECT_ID` | **DOLDURULMALI** | cloud.walletconnect.com (Reown) üzerinden ücretsiz Project ID al |
| `REACT_APP_ROBINHOOD_*` | GERÇEK | Robinhood Chain mainnet ayarları |
| `REACT_APP_METAMASK_*` | VARSAYILAN | MetaMask deep-link/indirme linkleri |
| `REACT_APP_BACKEND_URL` | preview URL | Deploy'da platform otomatik günceller / lastzhood.fun olacak |

## Deploy notu
Backend domaini `lastzhood.fun` olacak. Deploy ederken `PUBLIC_APP_URL`, `ADMIN_ORIGIN`,
`ADMIN_PROXY_ORIGIN` ve `REACT_APP_BACKEND_URL` değerlerini `https://lastzhood.fun` ile
güncellemek gerekebilir (frontend + backend aynı domain).
