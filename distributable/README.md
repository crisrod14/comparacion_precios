# 📦 Distributable - Ejecutable WOM Precios

Esta carpeta contiene todo lo necesario para **crear un ejecutable (.exe)** de la aplicación de comparación de precios.

## 🚀 Cómo generar el ejecutable

### Opción 1: Automático (Recomendado)
1. **Abre una terminal** en esta carpeta (`distributable/`)
2. **Ejecuta:**
   ```bash
   BUILD_EXECUTABLE.bat
   ```
3. **Espera** a que termine (puede tardar 2-3 minutos)
4. El ejecutable estará en: `distributable/dist/WOM_Precios.exe`

### Opción 2: Manual
```bash
# Instalar PyInstaller
pip install pyinstaller

# Generar ejecutable
pyinstaller --onefile --windowed --name "WOM_Precios" launcher.py
```

## 📋 Requisitos previos

- **Windows 7+** (para ejecutar el .exe)
- **Python 3.8+** (solo para crear el ejecutable)
- **Internet** (para descargar dependencias)

## 📤 Compartir el ejecutable

Una vez generado, puedes:

1. **Email directo**
   - Envía `WOM_Precios.exe` directamente

2. **Crear un ZIP**
   ```bash
   # Copia WOM_Precios.exe a una carpeta
   # Comprime la carpeta
   # Envía el ZIP
   ```

3. **Compartir por Drive/Dropbox**
   - Sube `WOM_Precios.exe` a tu nube preferida
   - Comparte el enlace

## 🖥️ Cómo usar el ejecutable

Los usuarios solo necesitan:
1. **Descargar** `WOM_Precios.exe`
2. **Hacer doble click** para ejecutar
3. **Se abre automáticamente** en el navegador

¡No necesitan instalar Python ni nada más!

## 📝 Notas importantes

- El ejecutable es **independiente** (self-contained)
- Contiene todas las dependencias necesarias
- El tamaño será de ~150-200 MB (es normal)
- Algunos antivirus pueden dar falsa alarma (es normal)

## 🔧 Solución de problemas

**"No se abre"**
- Revisa que Python esté instalado: `python --version`
- Intenta ejecutar `BUILD_EXECUTABLE.bat` de nuevo

**"PyInstaller no encontrado"**
- Ejecuta: `pip install pyinstaller`

**Antivirus bloquea el ejecutable**
- Es una falsa alarma de seguridad
- Agrega el .exe a las excepciones del antivirus

## 📞 Soporte

Si algo no funciona, revisa:
1. La consola de errores (mantén la ventana abierta)
2. Que Python esté en el PATH
3. Que tengas permisos de escritura en la carpeta
