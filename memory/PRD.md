# LastZHood — bağımsız yerel oyun ve Early

## Orijinal istekler
1. `https://github.com/Dostarki/offlinelast bu projeyi çek ve çalıştır.` Online mod tamamen offline hesaplanacak. Her oyuncunun kendi dünyasında admin panelindeki sayıda zombi ve rastgele doğan bot askerler olacak. Oyuncular birbirini görmeyecek; puanlar veritabanına kaydedilecek, gerçek oyuncu sayısı ve leaderboard online kalacak.
2. Kullanıcı seçimleri: oyun tarayıcıda yerel çalışırken puanlar/gerçek oyuncu sayısı online; botlar hem oyunculara hem zombilere saldıracak; botlar oyuncuya özel. Sıfır lag garantisi verilemez, cihaz/GPU performansı ayrı sınırdır.
3. `https://github.com/Dostarki/oyunforum bu repoyu çekerek sayfayı /early olarak oluştur. Main menüde navbara Early butonu da ekle. Bunun veritabanı ayrı olacak.` DB_NAME2 ve MONGO_URL2 kullanıcı tarafından sağlandı, yalnız backend/.env içinde. Canlı alan adı lastzhood.fun; kullanıcı önizleme API adresinin korunmasını onayladı.

## Mimari
- React/Three.js/Cannon mevcut grafikler ve arayüzler korunur.
- Python/Pymunk oyun motoru tarayıcı Web Worker'ında Pyodide 0.29.3 + uyumlu Pymunk 7.2.0 WASM ile çalışır. Sunucu native Pymunk 7.3.0 kullanır; paylaşılan oyun kaynakları aynı.
- `scripts/package_local_engine.py`: sadece oyun modüllerini ZIP yapar. Auth/DB/ödeme dosyaları veya .env ASLA dağıtılmaz. Runtime/whl dosyaları yerel statik olarak sunulur. İlk yükleme önceki sürümden daha büyüktür.
- `/api/join` mevcut imzalı cüzdan + ücretli erişim şartını korur. `/api/ws/{token}` yalnız presence/settings/leaderboard/report taşır; hareket/hasar/koordinat paylaşmaz. Sunucu `game.run()` çalıştırmaz.
- Yerel raporlar sınırlı/izinli alanlar, idempotent sıra numarası ve CAS/receipt ile yazılır; bağımsız satın alma haklarına müdahale etmez. İstemci hesaplı skor tam anti-cheat değildir, nakit/token ödül için güvenilir kabul edilmemelidir.
- Online sayı yalnız bağlı insan hesapları, botlar hariç; 3sn heartbeat/12sn timeout, 2sn sosyal güncelleme. Yerel input RTT ve NET RTT ayrı gerçek ölçümlerdir.
- Bağlantı kesilince simülasyon devam eder; rapor tekrar dener. Son checkpoint localStorage + pagehide beacon ile kurtarılır.
- Early kaynakları `backend/early`, `frontend/src/early`; bağımsız FastAPI alt uygulama `/api/early`, ayrı Mongo client yalnız `MONGO_URL2`/`DB_NAME2`. Admin cookie path ve JWT anahtarı ayrıdır; mevcut admin şifresi overwrite edilmez.
- Early tasarımının CSS'i `scripts/scope_early_styles.js` ile scope edilir. `/early`, `/early/console`, `/early/agent/:refCode`, `/early/admin`; oyun ana menüsü ve navbarında Early bağlantısı.
- Frontend API adresi mevcut REACT_APP_BACKEND_URL. Canlıda bu değişken lastzhood.fun olmalı; önizleme korunmuştur. Early public invite URL backend env'de lastzhood.fun/early.

## Uygulananlar / doğrulama
- İki repo indirildi, mevcut .git/.emergent ve korumalı env değerleri korundu.
- Bağımlılıklar kuruldu, oyun-only WASM paketi üretildi, servisler supervisor altında.
- Dış `/api/status` 200 ve simulation=local; ana sayfa ve Early menü geçişi screenshot ile doğrulandı.
- Henüz ayrıntılı oyun/bağımsız dünya/progress test raporu bekleniyor.

## Bilinen engel ve backlog
- P0: Kullanıcının sağladığı ikinci MongoDB sunucularında TCP 27017 bağlantısı timeout; `/api/early/config` doğru biçimde 503 döner. Yerel DB'ye veya sahte veriye fallback YOK. Early bağlantı hatası artık oyunu durdurmaz. Ağ erişimi çözülünce mevcut yapı otomatik yeniden dener.
- P0: Yerel oyun motoru + bağımsız iki dünya + skor tekrar deneme + bot/zombi sayıları testleri.
- P1: Gerçek cihazlarda WASM yükleme ve 600 zombi/200 bot performansı; sıfır gecikme veya belirli FPS garantisi yok.
- P1: Reown Project ID kaynak repoda yok; injected cüzdan çalışacak şekilde conditional config. QR WalletConnect için uygulamaya ait ID gerekir; sahte ID eklenmedi.
- P1: Daha güçlü admin oyun parolası; rekabetçi leaderboard için sunucu replay/anti-cheat tasarımı.
- P2: Runtime caching/service worker ve performans profilleme; bot zorluk ayarı.

## Sonraki görev
Testing agent raporunu oku, tüm kapsam içi hataları gider; Early dış DB erişim engelini kullanıcıya açıkça bildir.

## Deploy hazırlığı (bu oturum)
- Repo `Dostarki/offlinegamezone` çekilip /app'e kuruldu (backend + frontend + scripts + public/local-runtime WASM).
- backend/.env: kullanıcının Atlas MONGO_URL/DB_NAME + tüm sağlanan değerler (JWT, ADMIN_PASSWORD_HASH, Robinhood, Coinbase, Treasury, EARLY_*, X_*, FXTWITTER_*). CORS_ORIGINS'e önizleme origin eklendi; lastzhood.fun/www korunur.
- frontend/.env: REACT_APP_BACKEND_URL (önizleme; deploy'da canlı domain ile override edilir), REACT_APP_ROBINHOOD_CHAIN_ID=4663, RPC, EXPLORER=https://robinhoodchain.blockscout.com, METAMASK wallet/download linkleri.
- requirements.txt: çakışan tekrar eden `litellm @ URL` satırı kaldırıldı (emergentintegrations aynı wheel'i transitif getiriyor) — deploy pip install artık temiz (dry-run exit=0).
- Vendored Pyodide `pyodide.asm.js` için lint ignore: /app/.oxlintrc.json, frontend/.oxlintrc.json, frontend/.eslintignore.
- Frontend webpack derlemesi başarılı (yalnız source-map uyarıları). Backend `server.py` 57 route ile import oluyor.
- ENGEL (yalnız önizleme): bu önizleme ortamından Atlas'a giden TCP 27017 engelli; backend önizlemede açılmıyor. Kullanıcı Atlas'ta 0.0.0.0/0 whitelist yaptı; deploy/canlı ortamda bağlantı çalışacak. Kullanıcı isteği: test yapma, kendisi deploy edecek.

## Son kullanıcı talepleri / devam durumu
- Kullanıcı cüzdan uzantısı ile `Cannot read properties of undefined (reading 'id')` bildirdi. Window.ethereum ile aynı çökme tarayıcıda yeniden üretildi. `walletConfig.js` injected-only modunda eksik rkDetails gönderen doğrudan createConnector çağrısı kaldırıldı; her iki dal connectorsForWallets kullanıyor. Sonrasında render+chooser açılıyor; zorunlu testing_agent regresyonu henüz bekliyor.
- Kullanıcının "her şey tamamsa deploylucam" mesajına henüz tamamen hazır olmadığı açıklandı. Yayınlama yapılmadı/istenmedi; kullanıcı kendisi yapacağını belirtti.
- Son istek: botlar başlangıç noktasına yığılmasın, haritanın rastgele yerlerinde doğsun; zombi 600 sınırı kalksın. Açık kullanıcı tercihi: üst sınır tamamen kalksın, admin sıfır veya istediği pozitif tam sayıyı girsin.
- Bot spawn/respawn artık 64 bölgeyi dengeleyen rastgele açık alan koordinatları; insan başlangıcı (0,0) korunur, güvenli alan/duvarlardan ve mümkün olduğunca mevcut aktörlerden uzak.
- Zombie_count modelindeki le=600, UI max/clamp ve legacy spawn_enemies 600 limiti kaldırıldı. Negatif/kesirli/boş giriş hata gösterir. Büyük nüfusun cihaz/yükleme maliyeti panelde yazılır.
- Yerel dünya başlangıcı artık sabit100 döngüyle sınırlı değil: prepare_step ile hedefe kadar parçalı oluşturma, arayüz ilerleme mesajı ve iptal düğmesi.
- Sonraki: yeni spawn + >600/0 ayar + WASM hedefpopülasyon + bildirilen wallet crash testlerini çalıştır; /play gerçek signed test-wallet akışını doğrula. Tests/browser_wallet_fixture.py hazır disposable fixture sağlar. Özel anahtar SADECE test fixture, gerçek transfer yapılmaz.
## Bug fix (bu oturum) — "PREPARING WORLD" takılması
- Belirti: Cüzdan + ödeme sonrası Start Game, "PREPARING WORLD / PREPARING WESTFALL" ekranında sonsuz bekliyordu.
- Kök neden: frontend/public/local-runtime/ içinde Pyodide paket wheel'leri (micropip, pydantic, pydantic_core, cffi, pycparser, typing_extensions, typing_inspection, annotated_types) ve pymunk-7.2.0 + pathfinding-1.0.22 wheel'leri eksikti. Bu yollar SPA index.html fallback'i (HTML) döndürüyordu; Pyodide loadPackage/micropip.install hata veriyor, worker "PREPARING WORLD" sonrası ilerleyemiyordu.
- Çözüm: `python scripts/package_local_engine.py --runtime` çalıştırılarak tüm runtime wheel'leri CDN'den indirildi (15 asset doğrulandı). Wheel'ler artık application/octet-stream olarak servis ediliyor.
- Doğrulama: Gerçek tarayıcıda local-game.worker.js tam boot oldu (DOWNLOADING -> ... -> PREPARING WORLD 250/250 -> WORLD READY/open). Testing agent frontend %100 geçti (iteration_1.json).

## Oturum: Admin origin kaldırma + mobil cüzdan seçenekleri
- Oyun admin (/api/admin): `admin_auth.py` içindeki `check_origin` no-op yapıldı. Artık giriş yalnızca operator şifresiyle, herhangi bir origin/domain'den çalışır. 5 denemelik brute-force limiti ve bcrypt şifre doğrulaması korunur. Doğrulama: yabancı Origin ile login 200, yanlış şifre 401.
- Mobil cüzdan: Kullanıcı WalletConnect/Reown Project ID verdi; frontend/.env'e REACT_APP_WALLETCONNECT_PROJECT_ID eklendi. walletConfig.js artık projectId koşuluna bağlı olmadan HER ZAMAN tam markalı cüzdan listesini gösteriyor (metaMaskInjectedWallet, rainbowWallet, coinbaseWallet, walletConnectWallet + injectedWallet). Enjekte sağlayıcı olmasa bile MetaMask/Rainbow/Coinbase/WalletConnect/Browser Wallet görünüyor (tarayıcıda doğrulandı). Mobilde MetaMask seçilince, enjekte yoksa metamask.app.link deep-link ile yüklü MetaMask uygulaması açılır.
- Not: CRA'yı import anında çökerten MetaMask SDK'dan kaçınmak için orijinal özel metaMaskInjectedWallet korundu (mobil deep-link'i getWalletConnectConnector + metamask.app.link üzerinden yapıyor). Gerçek mobil cihazda uygulama açılışı otomasyonla test edilemez.
- Deploy: kullanıcı "daha sonra ben haber veririm" dedi; yayınlama YAPILMADI.

## Oturum: Mobil kontroller — kaydırmalı çift joystick
- Eski 4 yönlü D-pad + tek ateş butonu kaldırıldı (HUD.jsx). Yerine iki analog kaydırmalı joystick geldi:
  - Sol "MOVE": sürükleyerek sürekli hareket (engine.touchMove = normalize {x,y}; eski D-pad semantiği birebir korundu: sağ={1,0}, yukarı={0,-1}).
  - Sağ "AIM · FIRE": sürükleyerek manuel nişan + yön dönüşü; deadzone (0.25) aşılınca ateş başlar. Açı, hareketle aynı izometrik baza göre atan2(nx+ny, -nx+ny) ile hesaplanır, yani çubuğu ittiğiniz ekran yönüne nişan alır/ateş eder.
- renderer.js: `aimStick` bayrağı eklendi; aktifken otomatik en-yakın-zombi hedeflemesi devre dışı, açı doğrudan sağ joystick'ten gelir. tryLocalFire zaten this.angle yönünde ateş ediyor; açı input.angle ile sunucuya da gider. blur'da aimStick sıfırlanır.
- App.css: .mobile-stick (130px daire, sol alt / sağ alt, bottom:150px) köşe panellerinin (vitals/ammo bottom:21px) üstünde konumlandı; artık HUD ile çakışmıyor. Thumb sürükleme ile hareket eder.
- Doğrulama: webpack derlemesi başarılı (yalnız source-map uyarıları), sayfa 200. Joystick giriş matematiği Node ile doğrulandı (hareket eşlemesi + nişan açısı + ateş deadzone). Oyun-içi görsel, cüzdan+ödeme gerektirdiği için önizleme otomasyonunda ekran görüntüsüyle alınamadı; gerçek telefonda kullanıcı doğrulaması önerilir.

## Oturum: Sağ-alt silah kartı ↔ ateş joystick çakışması
- Belirti: Sağ alttaki AIM/FIRE joystick'i ile silah/cephane kartı (Glock 18) ve Q/F iyileştirme butonları üst üste biniyordu.
- Çözüm: Bu öğeleri saran `.hud-right-bottom` mobil konumu `right:30;bottom:60` → `right:14;bottom:298` olarak yukarı taşındı (App.css, @media max-width:767). Joystick üst kenarı ~280px olduğundan kart artık onun hemen üstünde, çakışma yok. Kart + heal butonları birlikte sağ-üste alındı (kullanıcı isteği "silahı hafif sağ üste koy").
- Derleme temiz, sayfa 200. Önizleme ekran-görüntü aracı mobil viewport emüle edemediği ve oyun ödeme-kapılı olduğu için oyun-içi mobil görünüm burada kanıtlanamadı; telefonda doğrulama önerilir.

## Oturum: AIM joystick hep sağa ateş ediyordu → 360° düzeltme
- Kök neden: Sağ joystick sürüklenirken global `pointermove` (renderer this.mouse) parmağın EKRAN konumundan (sağ tarafta) nişanı yeniden hesaplayıp joystick açısını eziyordu → hep sağa.
- Çözüm: this.mouse içindeki açı güncellemesine `&& !this.aimStick` koşulu eklendi. Artık aim stick aktifken global işleyici araya girmiyor; açı yalnız joystick yönünden geliyor. 8 yön testi 45° aralıklarla tam 360° veriyor, hareket bazıyla tutarlı. Derleme temiz, 200.

## Oturum: İlk cüzdan bağlantısında tek seferlik nick girişi + istediğinde değiştirme
- Backend (player_auth.py verify + server.py WalletAuthResponse): yeni hesap ilk kez oluşturulduğunda yanıta `new_account: true` eklendi (ikinci girişte false).
- Frontend authContext: loginWithWallet dönüşüne new_account taşındı.
- WalletGate: nick modalı artık ödeme (game_access) şartına bağlı DEĞİL; yalnızca `acct.new_account` olduğunda (ilk bağlantı) bir kez açılıyor. Kullanıcı skip ederse tekrar otomatik açılmaz.
- "İstediğinde değiştir": bağlı rozetine kalem (Pencil) butonu eklendi → mevcut nick ile modalı açar, updateProfile(/api/auth/profile) ile kaydeder. Modal başlığı/metni duruma göre REGISTER/CHANGE; modal içinde inline hata (nick dolu vb.).
- Uçtan uca doğrulandı (eth_account ile SIWE): ilk giriş new_account=true, ikinci false; /auth/profile ile nick değişimi kalıcı ve /auth/me'de görünüyor. Derleme temiz, konsol hatası yok.
