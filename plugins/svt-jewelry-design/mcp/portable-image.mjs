import { createRequire } from "node:module";
import { inflateSync } from "node:zlib";

const require = createRequire(import.meta.url);
let jpeg;

const MAX_PREVIEW_PIXELS = 4096 * 4096;
const MAX_INFLATED_BYTES = 68 * 1024 * 1024;

function assertSafeDimensions(width, height, channels, label) {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1) {
    throw new Error(`${label} has invalid dimensions`);
  }
  const pixels = width * height;
  const decodedBytes = pixels * channels;
  if (!Number.isSafeInteger(pixels) || pixels > MAX_PREVIEW_PIXELS || decodedBytes > MAX_INFLATED_BYTES) {
    throw new Error(`${label} dimensions exceed the portable preview limit`);
  }
  return { pixels, decodedBytes };
}

function jpegCodec() {
  jpeg ||= require("./vendor/jpeg-js/index.js");
  return jpeg;
}

function paeth(left, above, upperLeft) {
  const estimate = left + above - upperLeft;
  const leftDistance = Math.abs(estimate - left);
  const aboveDistance = Math.abs(estimate - above);
  const diagonalDistance = Math.abs(estimate - upperLeft);
  if (leftDistance <= aboveDistance && leftDistance <= diagonalDistance) return left;
  return aboveDistance <= diagonalDistance ? above : upperLeft;
}

function decodePng(buffer) {
  if (!buffer.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) throw new Error("invalid PNG signature");
  let cursor = 8;
  let header;
  let palette;
  let transparency;
  const imageData = [];
  while (cursor + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(cursor);
    if (length > buffer.length - cursor - 12) throw new Error("PNG chunk exceeds the source buffer");
    const type = buffer.toString("ascii", cursor + 4, cursor + 8);
    const data = buffer.subarray(cursor + 8, cursor + 8 + length);
    if (type === "IHDR") header = data;
    else if (type === "PLTE") palette = data;
    else if (type === "tRNS") transparency = data;
    else if (type === "IDAT") imageData.push(data);
    else if (type === "IEND") break;
    cursor += length + 12;
  }
  if (!header || imageData.length === 0) throw new Error("PNG is missing IHDR or IDAT data");
  const width = header.readUInt32BE(0);
  const height = header.readUInt32BE(4);
  const bitDepth = header[8];
  const colorType = header[9];
  const interlace = header[12];
  const channels = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[colorType];
  if (bitDepth !== 8 || !channels || interlace !== 0) throw new Error("PNG preview supports non-interlaced 8-bit images");
  if (colorType === 3 && !palette) throw new Error("indexed PNG is missing its palette");
  const { pixels } = assertSafeDimensions(width, height, channels, "PNG");
  const rowBytes = width * channels;
  const expectedInflatedBytes = (rowBytes + 1) * height;
  if (!Number.isSafeInteger(expectedInflatedBytes) || expectedInflatedBytes > MAX_INFLATED_BYTES) {
    throw new Error("PNG decompressed data exceeds the portable preview limit");
  }
  const inflated = inflateSync(Buffer.concat(imageData), { maxOutputLength: expectedInflatedBytes });
  if (inflated.length !== expectedInflatedBytes) throw new Error("PNG pixel data has an unexpected size");
  const raw = Buffer.alloc(rowBytes * height);
  for (let y = 0; y < height; y += 1) {
    const sourceOffset = y * (rowBytes + 1);
    const outputOffset = y * rowBytes;
    const filter = inflated[sourceOffset];
    for (let x = 0; x < rowBytes; x += 1) {
      const encoded = inflated[sourceOffset + x + 1];
      const left = x >= channels ? raw[outputOffset + x - channels] : 0;
      const above = y > 0 ? raw[outputOffset + x - rowBytes] : 0;
      const upperLeft = y > 0 && x >= channels ? raw[outputOffset + x - rowBytes - channels] : 0;
      const predictor = filter === 0 ? 0
        : filter === 1 ? left
          : filter === 2 ? above
            : filter === 3 ? Math.floor((left + above) / 2)
              : filter === 4 ? paeth(left, above, upperLeft)
                : null;
      if (predictor === null) throw new Error(`unsupported PNG filter ${filter}`);
      raw[outputOffset + x] = (encoded + predictor) & 0xff;
    }
  }
  const data = Buffer.alloc(pixels * 4);
  for (let pixel = 0; pixel < pixels; pixel += 1) {
    const source = pixel * channels;
    const target = pixel * 4;
    if (colorType === 6) raw.copy(data, target, source, source + 4);
    else if (colorType === 2) {
      data[target] = raw[source]; data[target + 1] = raw[source + 1]; data[target + 2] = raw[source + 2]; data[target + 3] = 255;
    } else if (colorType === 0) {
      data[target] = raw[source]; data[target + 1] = raw[source]; data[target + 2] = raw[source]; data[target + 3] = 255;
    } else if (colorType === 4) {
      data[target] = raw[source]; data[target + 1] = raw[source]; data[target + 2] = raw[source]; data[target + 3] = raw[source + 1];
    } else {
      const paletteOffset = raw[source] * 3;
      data[target] = palette[paletteOffset] || 0;
      data[target + 1] = palette[paletteOffset + 1] || 0;
      data[target + 2] = palette[paletteOffset + 2] || 0;
      data[target + 3] = transparency?.[raw[source]] ?? 255;
    }
  }
  return { width, height, data };
}

function jpegDimensions(buffer) {
  if (buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) throw new Error("invalid JPEG signature");
  const startOfFrame = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);
  let cursor = 2;
  while (cursor < buffer.length) {
    while (cursor < buffer.length && buffer[cursor] !== 0xff) cursor += 1;
    while (cursor < buffer.length && buffer[cursor] === 0xff) cursor += 1;
    if (cursor >= buffer.length) break;
    const marker = buffer[cursor];
    cursor += 1;
    if (marker === 0xd8 || marker === 0xd9 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (cursor + 2 > buffer.length) throw new Error("JPEG segment is truncated");
    const length = buffer.readUInt16BE(cursor);
    if (length < 2 || cursor + length > buffer.length) throw new Error("JPEG segment exceeds the source buffer");
    if (startOfFrame.has(marker)) {
      if (length < 8) throw new Error("JPEG frame header is truncated");
      return { width: buffer.readUInt16BE(cursor + 5), height: buffer.readUInt16BE(cursor + 3) };
    }
    cursor += length;
  }
  throw new Error("JPEG is missing a supported frame header");
}

function resizeRgba(image, maxDimension) {
  const scale = Math.min(1, maxDimension / Math.max(image.width, image.height));
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));
  if (width === image.width && height === image.height) return image;
  const data = Buffer.alloc(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    const sourceY = Math.min(image.height - 1, Math.floor((y + 0.5) * image.height / height));
    for (let x = 0; x < width; x += 1) {
      const sourceX = Math.min(image.width - 1, Math.floor((x + 0.5) * image.width / width));
      const source = (sourceY * image.width + sourceX) * 4;
      const target = (y * width + x) * 4;
      image.data.copy(data, target, source, source + 4);
    }
  }
  return { width, height, data };
}

function flattenOnWhite(image) {
  const data = Buffer.from(image.data);
  for (let offset = 0; offset < data.length; offset += 4) {
    const alpha = data[offset + 3] / 255;
    data[offset] = Math.round(data[offset] * alpha + 255 * (1 - alpha));
    data[offset + 1] = Math.round(data[offset + 1] * alpha + 255 * (1 - alpha));
    data[offset + 2] = Math.round(data[offset + 2] * alpha + 255 * (1 - alpha));
    data[offset + 3] = 255;
  }
  return { ...image, data };
}

function encodeJpeg(image, quality) {
  const encoded = jpegCodec().encode(flattenOnWhite(image), Math.max(20, Math.min(90, quality)));
  return { mimeType: "image/jpeg", data: Buffer.from(encoded.data) };
}

function compactImage(image, maxDimension, quality) {
  const source = Buffer.isBuffer(image.data) ? image.data : Buffer.from(image.data, "base64");
  if (image.mimeType === "image/png") {
    const resized = resizeRgba(decodePng(source), maxDimension);
    return encodeJpeg(resized, quality);
  }
  if (image.mimeType === "image/jpeg") {
    const dimensions = jpegDimensions(source);
    assertSafeDimensions(dimensions.width, dimensions.height, 4, "JPEG");
    const decoded = jpegCodec().decode(source, {
      useTArray: true,
      formatAsRGBA: true,
      maxResolutionInMP: 17,
      maxMemoryUsageInMB: 128,
    });
    if (decoded.width !== dimensions.width || decoded.height !== dimensions.height) throw new Error("JPEG decoded dimensions do not match its frame header");
    const resized = resizeRgba({ ...decoded, data: Buffer.from(decoded.data) }, maxDimension);
    return encodeJpeg(resized, quality);
  }
  throw new Error(`portable preview compression does not support ${image.mimeType}`);
}

export { compactImage };
