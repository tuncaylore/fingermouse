# 🖐️ FingerMouse

[![Windows tests](https://github.com/tuncaylore/fingermouse/actions/workflows/tests.yml/badge.svg)](https://github.com/tuncaylore/fingermouse/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Windows 10/11 üzerinde **web kamerasıyla eli takip edip fareyi kontrol eden** Python projesi.

## Özellikler

- İşaret parmağıyla imleç kontrolü; sol/sağ tık, sürükle-bırak ve kaydırma.
- Titremeyi azaltan hareket yumuşatma ve parmak birleştirme eşikleri.
- Kullanıcıya özel hareket eğitimi, örnek toplama ve tanıma doğrulaması.
- T menüsünde ayrı sol çift tıklama hareketi eğitimi (**6**).
- Açık onayla etkinleştirilen pencere kapatma hareketi (Alt+F4).
- Kamera seçimi, canlı el eklemleri ve FPS göstergesi.
- Duraklatma, el kaybolunca fareyi bırakma ve ekran köşelerinde güvenlik durdurması.
- Python kontrolü, gerektiğinde kurulum, yerel sanal ortam ve otomatik paket kurulumu.
- Kamera görüntülerinin ve hareket eğitiminin yerel işlenmesi.
- Yeni kamera karesi için bildirim tabanlı bekleme; gereksiz kare kopyalama ve tekrar işleme yok.

[Sürüm notları](CHANGELOG.md) · [GitHub sürümleri](https://github.com/tuncaylore/fingermouse/releases)

## Tek tıkla çalıştırma

1. [Projeyi ZIP olarak indirin](https://github.com/tuncaylore/fingermouse/archive/refs/heads/main.zip) ve **tamamını ZIP'ten çıkarın**.
2. **[`run.bat`](run.bat) dosyasına çift tıklayın.** Python kontrol edilir, `.venv` bilgisayarınızda oluşturulur ve gerekli paketler yüklenir. İlk uygulama açılışında Google'ın el takip modeli indirilir. İlk kurulumda internet gerekir.
3. Kamera erişimine izin verin. Açılan pencerede elinizi kameraya gösterin.

**`.venv` indirmeniz gerekmez; repoya dahil değildir ve başlatıcı tarafından yerel olarak oluşturulur.** Paket listesi değişmemişse ve kurulum sağlıklıysa sonraki açılışlarda tekrar indirme yapılmaz. Model de indirildikten sonra çevrimdışı çalışabilirsiniz.

### Gereksinimler

- Windows 10/11 (64-bit), web kamerası ve kamera erişim izni.
- Python 3.10–3.13 (64-bit); önerilen sürüm **3.12**.
- İlk kurulum için internet ve klasöre yazma izni.
- Python yoksa otomatik kurulum için Windows App Installer / `winget`.

Python yüklü değilse başlatıcı `winget` ile **Python 3.12 (64-bit)** kurmayı dener. `winget` yoksa veya kurulum başarısızsa hata gösterir; [python.org](https://www.python.org/downloads/windows/) adresinden Python 3.12 (64-bit) yükleyip **Add python.exe to PATH** seçeneğini işaretleyin ve tekrar çalıştırın.

Komut İstemi'nden:

```bat
run.bat
run.bat 1
run.bat --help
```

`1` ikinci kamerayı seçer. `--help` kurulum kontrolünü yapıp komut yardımını gösterir; kamerayı açmaz ve modeli indirmez.

## Hareketler

| Hareket | İşlem |
|---|---|
| Yalnızca işaret parmağı yukarı | Fare imlecini hareket ettir |
| Başparmak + işaret parmağını birleştir, sonra ayır | Sol tık |
| Başparmak + işaret parmağını birleştirip elde tutarak hareket et | Sürükle, ayırınca bırak |
| Başparmak + orta parmağı birleştir | Sağ tık |
| İşaret + orta parmağı yukarı kaldır, elini yukarı/aşağı götür | Sayfa kaydır |
| Avucu kapat veya elini kameradan çek | Fare hareketini bırak |
| **T** | Hareket tanımlama menüsünü aç / kapat |
| **SPACE (boşluk)** | Duraklat / devam et (kamera penceresindeyken) |
| **ESC** | Çık (kamera penceresindeyken) |

## Hareket tanımlama (eğitim)

**T** tuşuna basın ve menüden eylem seçin:

| Tuş | İşlem |
|---|---|
| **1** | Sol tık hareketini tanımla |
| **2** | Sağ tık hareketini tanımla |
| **3** | Pencereyi kapat hareketini tanımla (onay gerekir) |
| **4** | Tüm eğitimi sil (iki kez basın) |
| **5** | Pencere kapatmayı devre dışı bırak |
| **6** | Sol çift tıklama hareketini tanımla |
| **X** | Özel hareketleri aç / kapat |

Bir eylem seçtiğinizde kamera eğitim moduna geçer. Geri sayımı bekleyin, hareketi yapıp yaklaşık 2 saniye sabit tutun. Yeterli örnek yoksa veya hareket kararsızsa uygulama yeniden denemenizi ister. Yeterli örnek toplanınca doğrulama aşaması başlar; aynı hareketi tekrar yaptığınızda tanınırsa eğitim tamamlanır ve `gestures.json` dosyasına kaydedilir. Eğitim verisi bilgisayarınızdan çıkmaz.

- **ENTER:** Başarısız eğitimi tekrar dene / tamamlanan eğitimden menüye dön.
- **R:** Başarısız eğitimde yalnızca seçilen eylemi sıfırla.
- **ESC:** Eğitimi iptal et ve menüye dön.

### Sol çift tıklama

**T → 6** ile sol tık ve sürüklemeden farklı bir el hareketi öğretin. Hareket çok benzerse eğitim kabul edilmez. Doğrulandıktan sonra bu hareketi yaptığınızda iki sol tık gönderilir; hareketi sabit tutmak tekrar tekrar tıklamaz. Yeniden tetiklemek için önce hareketi bırakıp tekrar yapın.

İki tık arasındaki hedef süre 100 ms'dir; ikinci tık ilk uygun kamera karesinde gönderilir, kamera döngüsü bekletilmez. Arada el kaybolursa, duraklatırsanız, menüyü açarsanız veya güvenlik durdurması olursa bekleyen ikinci tık iptal edilir. Mevcut sol tık ve sürükleme davranışı değişmez; eski eğitimler kullanılmaya devam eder.

> **Güvenlik:** Pencereyi kapatma eylemi varsayılan olarak kapalıdır ve yalnızca açık onayla etkinleşir. Hatalı tanıma durumunda menüden **5** ile hemen devre dışı bırakabilir veya **X** ile tüm özel hareketleri kapatabilirsiniz.

> **İpucu:** Avucunuz yaklaşık 30-60 cm mesafede, yüzünüz aydınlık ve arka plan sade olsun. Hareketi küçültmek için kameranın orta alanını kullanın.

## Sorun giderme

- **Kamera açılmıyor:** Windows Ayarlar > Gizlilik ve güvenlik > Kamera bölümünden masaüstü uygulamalarına izin verin; Zoom/Teams/kamera kullanan uygulamaları kapatın.
- **Harici kamera seçme:** `run.bat` kısayolunun hedefinin sonuna ` 1` ekleyin veya Komut İstemi'nden `run.bat 1` çalıştırın.
- **Python / paket kurulumu hata veriyor:** Python 3.12 (64-bit) kullanın. İnternet, pip erişimi ve güvenlik duvarını kontrol edin.
- **OpenCV paket çakışması:** Başlatıcı eski `.venv` içindeki `opencv-python` ve headless varyantlarını tespit eder, kaldırır ve paketleri yeniden kurar. Bu tek seferlik onarım internet gerektirir; `pip check` tek başına bu çakışmayı bulamaz.
- **Aşırı tıklama:** Başparmağınızı işaret/orta parmak ucundan uzak tutun; parmakları kameraya net gösterin.
- **Fare köşeye giderse:** PyAutoGUI güvenliği kontrolü duraklatır. Fiziksel fareyi ekran köşesinden uzaklaştırıp SPACE ile yeniden etkinleştirin.
- **Birden çok ekran:** İlk sürüm öncelikle ana ekranı kontrol eder.
- **Hatalı veya taşınmış sanal ortam:** Yalnızca bu projenin `.venv` klasörünü silip tekrar `run.bat` dosyasını açın. Kişisel eğitim dosyanız `gestures.json` ayrı tutulur.

## Teknoloji

- Python 3.10–3.13, OpenCV (`opencv-contrib-python`), MediaPipe **Tasks HandLandmarker API**, PyAutoGUI, NumPy.
- MediaPipe da aynı OpenCV paketini kullanır; çakışmayı önlemek için ayrıca `opencv-python` kurmayın.
- Video kamerada işlenir; görüntüler sunucuya gönderilmez. İlk kurulumda pip paketleri ve `hand_landmarker.task` modeli indirilir.
- Model: [Google MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python)
- Fare kontrolünde güvenlik amacıyla PyAutoGUI `FAILSAFE` açıktır.

## Gizlilik ve güvenlik

`gestures.json`, `.venv`, model dosyası ve önbellekler Git'e dahil edilmez. Her kullanıcı kendi eğitimini oluşturur. Kameradaki görüntüler uygulama tarafından sunucuya gönderilmez; paket ve model indirmeleri ilgili sağlayıcılara internet bağlantısı gerektirir.

İlk denemelerde kaydedilmemiş belgeleri kapatın ve fiziksel farenizi erişilebilir tutun. Pencere kapatma eylemi kaydedilmemiş çalışmalarınızı etkileyebilir; her açılışta yeniden onay gerekir. Bu proje deneysel bir masaüstü aracıdır; kritik işlemler için kullanmayın.

## Geliştirici testleri

Önce `run.bat --help` ile kurulumu tamamlayın, ardından:

```bat
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m py_compile fingermouse.py gesture_learning.py gesture_math.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions, Windows üzerinde Python 3.10–3.13 için kurulum, çevrimdışı başlatıcı tekrar kullanımı, eski OpenCV çakışmasının onarımı, hareket eğitimi ve sahte kamera/fare ile çalışma döngüsü testlerini çalıştırır. Canlı kamera ve gerçek fare hareketleri CI'da test edilmez; bunlar son kullanıcı Windows bilgisayarında doğrulanmalıdır.

## Katkı ve lisans

Hata bildirmek veya özellik önermek için [Issues](https://github.com/tuncaylore/fingermouse/issues), kod değişiklikleri için Pull Request kullanabilirsiniz. Hata bildirirken Windows/Python sürümünü ve hata metnini paylaşın; kamera görüntülerini veya kişisel eğitim verisini eklemeyin.

Proje kodu [MIT lisansı](LICENSE) ile sunulur. Üçüncü taraf paketler ve otomatik indirilen Google modeli kendi lisanslarına tabidir.
