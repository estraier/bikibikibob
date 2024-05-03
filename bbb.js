"use strict";

function main() {
  console.log("hello world");
  adjust_images();
}

function adjust_images() {
  for (const area of document.getElementsByClassName("image_area")) {
    const area_width = area.getBoundingClientRect().width;
    const images = area.getElementsByClassName("emb_image");
    const max_area = area_width * area_width * 3 / 4;
    for (const image of images) {
      const image_area = image.width * image.height;
      if (image_area > max_area) {
        image.width = image.width * (max_area / image_area);
      }
    }
  }
}
