"""Deriva tamanhos de instalação do ícone aprovado, sem redesenho ou distorção.
Requer Pillow apenas na preparação dos arquivos; o aplicativo não depende dele.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/branding/approved-icon.png'


def build():
    with Image.open(SOURCE) as source:
        # Recorte central quadrado: retira somente laterais do painel externo.
        # Mantém o botão e o símbolo luminoso completos, sem alongar a imagem.
        square = source.convert('RGB').crop((181, 0, 1267, 1086))
        for size in (192, 512):
            icon = square.resize((size, size), Image.Resampling.LANCZOS)
            icon.save(ROOT / f'icon-{size}.png', optimize=True)
            icon.save(ROOT / f'inspecao/dvor-vor/icon-{size}.png', optimize=True)
        square.resize((180, 180), Image.Resampling.LANCZOS).save(ROOT / 'apple-touch-icon.png', optimize=True)
        # O símbolo e o botão ficam dentro da área segura da máscara circular.
        masked = Image.new('RGB', (512, 512), '#0b1015')
        masked.paste(square.resize((352, 352), Image.Resampling.LANCZOS), (80, 80))
        masked.save(ROOT / 'icon-maskable-512.png', optimize=True)


def normal_cycle():
    """Copia os oito primeiros quadros GIF sem recomprimir pixels ou tempos."""
    data = (ROOT/'assets/branding/approved-apu.gif').read_bytes()
    end = 13 + (3 * 2 ** ((data[10] & 7) + 1) if data[10] & 128 else 0)
    result = bytearray(data[:end]); frames = 0
    while frames < 8:
        start = end; marker = data[end]; end += 1
        if marker == 0x21:
            end += 1
            while data[end]: end += data[end] + 1
            end += 1
            block = data[start:end]
            if b'NETSCAPE2.0' not in block: result.extend(block)
        elif marker == 0x2C:
            packed = data[end+8]; end += 9
            if packed & 128: end += 3 * 2 ** ((packed & 7) + 1)
            end += 1  # LZW minimum code size
            while data[end]: end += data[end] + 1
            end += 1
            result.extend(data[start:end]); frames += 1
        else:
            raise ValueError('Estrutura inesperada no GIF aprovado')
    result.append(0x3B)
    (ROOT/'assets/branding/apu-startup.gif').write_bytes(result)
    with Image.open(ROOT/'assets/branding/approved-apu.gif') as im:
        im.seek(7);im.convert('RGB').save(ROOT/'assets/branding/apu-ready.png',optimize=True)


if __name__ == '__main__':
    build()
    normal_cycle()
