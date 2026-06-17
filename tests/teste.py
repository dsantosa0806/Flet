""""
Criar executável Admin

pyinstaller --noconfirm --onefile --windowed --clean --name "RPA v1.4.1 Admin" --icon "images\iconApp.ico" --add-data "config.py;." --add-data "images;images" --version-file "version.txt" main_admin.py

Ou

pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --clean ^
  --name "RPA v1.4.1 Admin" ^
  --icon "images\iconApp.ico" ^
  --add-data "config.py;." ^
  --add-data "images;images" ^
  --version-file "version.txt" ^
  main_admin.py

Criar executável Usuario

pyinstaller --noconfirm --onefile --windowed --clean --name "RPA v1.4.1 Usuario" --icon "images\iconApp.ico" --add-data "config.py;." --add-data "images;images" --version-file "version.txt" main_usuario.py

ou

pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --clean ^
  --name "RPA v1.4.1 Usuario" ^
  --icon "images\iconApp.ico" ^
  --add-data "config.py;." ^
  --add-data "images;images" ^
  --version-file "version.txt" ^
  main_usuario.py

"""