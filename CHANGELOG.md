# Sürüm notları

## v0.2.0 — 2026-11-07

### Yeni

- **T → 6:** Ayrı bir sol çift tıklama hareketi eğitimi, doğrulama ve yerel kayıt.
- Çift tıklama kamera döngüsünü uyutmadan iki sol tık gönderir; hedef aralık 100 ms, ikinci tık ilk uygun kamera karesinde tamamlanır.
- Sabit tutulan hareket yalnızca bir kez tetiklenir. El kaybolması, duraklatma, menü ve güvenlik durdurması bekleyen ikinci tıklamayı iptal eder.
- Mevcut sol/sağ tık, sürükleme, pencere kapatma onayı ve eski eğitim dosyaları korunur.

### Performans

- Kamera okuyucusu 2 ms aralıklı sorgulama yerine yeni kare bildirimini bekler.
- Her karedeki gereksiz görüntü kopyası kaldırıldı; ana döngü görüntüyü ayrı bir diziye aynalar.
- Yeni kare gelmediğinde eski görüntü tekrar işlenmez; aynı kare tekrar eğitim/doğrulama örneği sayılmaz.
- Hareket sınıflandırmasındaki uzaklık hesabı sadeleştirildi. Yerel Python 3.12 sentetik üç-eylem ölçümünde, eski/yeni kod aynı süreçte karşılaştırıldığında medyan süre 5,53 µs'den 4,45 µs'ye düştü (yaklaşık %20). Bu bir sınıflandırma mikro ölçümüdür; canlı kamera FPS artışı iddiası değildir.

### Kurulum ve testler

- Eski ortamlarda aynı `cv2` dosyalarını paylaşan OpenCV paketlerinin çakışması tespit edilip yalnızca projenin `.venv` ortamında onarılır.
- Bozuk import veya tutarsız paket kurulumu durumunda paketler zorunlu yeniden kurulur; hatalar açıkça gösterilir.
- MediaPipe, OpenCV ve NumPy için hazır wheel paketleri kullanılır; desteklenmeyen platformlarda derleme denenmez.
- Windows CI'a OpenCV çakışması oluşturma/onarım testi ve kamera, çift tıklama, eğitim/kayıt regresyon testleri eklendi.
- Kamera donanımı ve gerçek masaüstü etkileşimi son kullanıcı bilgisayarında ayrıca test edilmelidir.

## İlk yayın — 2026-11-07

- FingerMouse adıyla public kaynak kodu, otomatik Windows başlatıcısı, kullanım rehberi ve MIT lisansı.
- Sol/sağ tık, sürükleme, kaydırma ve özel hareket eğitimi.
- Python 3.10–3.13 için Windows CI.
