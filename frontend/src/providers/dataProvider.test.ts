import { describe, it, expect } from 'vitest';
import { toFormDataIfNeeded } from './dataProvider';

describe('toFormDataIfNeeded', () => {
  describe('image / file field stripping', () => {
    it('strips an existing image URL string so DRF ImageField does not reject it', () => {
      const result = toFormDataIfNeeded({
        name: 'Apples',
        price: '2.50',
        image: 'https://cdn.example.com/products/apples.jpg',
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('image');
      expect(result.name).toBe('Apples');
      expect(result.price).toBe('2.50');
    });

    it('strips fields ending in _image', () => {
      const result = toFormDataIfNeeded({
        name: 'Bread',
        thumbnail_image: 'https://cdn.example.com/thumb.jpg',
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('thumbnail_image');
    });

    it('strips fields ending in _file', () => {
      const result = toFormDataIfNeeded({
        name: 'Doc',
        attachment_file: 'https://cdn.example.com/doc.pdf',
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('attachment_file');
    });

    it('still passes through a new file upload (rawFile)', () => {
      const mockFile = new File(['bytes'], 'photo.jpg', { type: 'image/jpeg' });
      const result = toFormDataIfNeeded({
        name: 'Carrots',
        image: { rawFile: mockFile, src: 'blob:...' },
      });

      expect(result).toBeInstanceOf(FormData);
      const fd = result as FormData;
      expect(fd.get('name')).toBe('Carrots');
      expect(fd.get('image')).toBe(mockFile);
    });

    it('passes through null image (clearing an image)', () => {
      const result = toFormDataIfNeeded({
        name: 'Eggs',
        image: null,
      }) as Record<string, unknown>;

      // null means the user explicitly cleared the image — preserve it so
      // DRF can set the field to null (allow_null=True on the serializer).
      expect(result).toHaveProperty('image', null);
    });
  });

  describe('object stripping (pre-existing ImageInput descriptor without rawFile)', () => {
    it('strips an object that has src but no rawFile', () => {
      const result = toFormDataIfNeeded({
        name: 'Milk',
        image: { src: 'https://cdn.example.com/milk.jpg' },
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('image');
    });
  });

  describe('empty string stripping', () => {
    it('strips empty string values', () => {
      const result = toFormDataIfNeeded({
        name: 'Butter',
        description: '',
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('description');
      expect(result.name).toBe('Butter');
    });

    it('sends null for a cleared translation column instead of dropping it', () => {
      const result = toFormDataIfNeeded({
        name_en: 'Butter',
        name_es: '',
        description_es: '',
      }) as Record<string, unknown>;

      expect(result).toHaveProperty('name_es', null);
      expect(result).toHaveProperty('description_es', null);
    });
  });

  describe('translated field handling (modeltranslation)', () => {
    it('strips the resolved base field when its explicit _en column is present', () => {
      // React-Admin submits the full record, so an edit to name_en arrives
      // alongside the stale resolved `name` — the base write would clobber
      // the name_en column on the server.
      const result = toFormDataIfNeeded({
        name: 'Apple',
        name_en: 'Green Apple',
        name_es: 'Manzana',
        description: 'Old',
        description_en: 'New description',
      }) as Record<string, unknown>;

      expect(result).not.toHaveProperty('name');
      expect(result).not.toHaveProperty('description');
      expect(result.name_en).toBe('Green Apple');
      expect(result.name_es).toBe('Manzana');
      expect(result.description_en).toBe('New description');
    });

    it('keeps the base field when no explicit _en column is present (create forms)', () => {
      const result = toFormDataIfNeeded({
        name: 'Bread',
        name_es: 'Pan',
      }) as Record<string, unknown>;

      expect(result.name).toBe('Bread');
      expect(result.name_es).toBe('Pan');
    });

    it('sends a cleared translation as blank on the multipart path', () => {
      const mockFile = new File(['bytes'], 'photo.jpg', { type: 'image/jpeg' });
      const result = toFormDataIfNeeded({
        name_en: 'Carrots',
        name_es: '',
        image: { rawFile: mockFile, src: 'blob:...' },
      });

      expect(result).toBeInstanceOf(FormData);
      const fd = result as FormData;
      expect(fd.get('name_en')).toBe('Carrots');
      expect(fd.get('name_es')).toBe('');
    });
  });

  describe('plain JSON path (no file upload)', () => {
    it('returns a plain object when there is no file to upload', () => {
      const result = toFormDataIfNeeded({
        name: 'Yogurt',
        price: '3.99',
        active: true,
        tag_ids: [1, 2],
      });

      expect(result).not.toBeInstanceOf(FormData);
      const obj = result as Record<string, unknown>;
      expect(obj.name).toBe('Yogurt');
      expect(obj.tag_ids).toEqual([1, 2]);
    });
  });
});
