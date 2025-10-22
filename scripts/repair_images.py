"""Script para remover imagens inválidas e de layout do banco de dados."""
import re
from app.repositories.db import SessionLocal
from app.domain.realestate import models as re_models
from sqlalchemy import select
from urllib.parse import urlparse


def is_valid_image_url(url: str | None) -> bool:
    """Valida se a URL da imagem tem domínio válido."""
    if not url:
        return False
    try:
        u = str(url).strip()
        if not (u.startswith('http://') or u.startswith('https://')):
            return False
        parsed = urlparse(u)
        return bool(parsed.hostname and '.' in parsed.hostname)
    except Exception:
        return False


def is_layout_image(url: str | None) -> bool:
    """Verifica se a imagem é de layout/site (não do imóvel)."""
    if not url:
        return False
    u = str(url).lower()
    
    # Se for do CDN de imóveis, NÃO é layout
    if 'cdn-imobibrasil.com.br/imagens/imoveis/' in u:
        return False
    
    # Padrões de imagens de layout
    layout_patterns = [
        r'logo', r'icon', r'banner', r'site_modelo', r'imagensct',
        r'redesp_', r'whatsapp_modulo', r'dcorretor', r'imobibrasil',
        r'facebook', r'instagram', r'youtube', r'twitter', r'diversos'
    ]
    return any(re.search(pattern, u) for pattern in layout_patterns)


def main():
    with SessionLocal() as db:
        # Buscar todas as imagens
        stmt = select(re_models.PropertyImage)
        images = db.execute(stmt).scalars().all()
        
        print(f"Total de imagens no banco: {len(images)}")
        
        # Classificar imagens
        invalid_images = [img for img in images if not is_valid_image_url(img.url)]
        layout_images = [img for img in images if is_valid_image_url(img.url) and is_layout_image(img.url)]
        valid_property_images = [
            img for img in images 
            if is_valid_image_url(img.url) and not is_layout_image(img.url)
        ]
        
        print(f"\n📊 Classificação:")
        print(f"  ✓ Imagens válidas de imóveis: {len(valid_property_images)}")
        print(f"  ⚠️  Imagens de layout/site: {len(layout_images)}")
        print(f"  ❌ Imagens com URL inválida: {len(invalid_images)}")
        
        to_remove = invalid_images + layout_images
        
        if to_remove:
            print(f"\n🗑️  Total a remover: {len(to_remove)}")
            
            if invalid_images:
                print("\nExemplos de URLs inválidas:")
                for img in invalid_images[:5]:
                    print(f"  - ID {img.id}, Property {img.property_id}: {img.url}")
            
            if layout_images:
                print("\nExemplos de imagens de layout:")
                for img in layout_images[:5]:
                    print(f"  - ID {img.id}, Property {img.property_id}: {img.url}")
            
            resposta = input("\nDeseja remover estas imagens? (s/n): ")
            if resposta.lower() == 's':
                for img in to_remove:
                    db.delete(img)
                db.commit()
                print(f"\n✓ {len(to_remove)} imagens removidas!")
                print(f"  - {len(invalid_images)} inválidas")
                print(f"  - {len(layout_images)} de layout")
            else:
                print("\nOperação cancelada.")
        else:
            print("\n✓ Nenhuma imagem para remover!")


if __name__ == "__main__":
    main()
