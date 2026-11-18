/** Restore native Godot linear albedo tints outside glTF's [0, 1] factor range.
 * Call once after GLTFLoader.loadAsync(), before caching/cloning the scene.
 * Idempotent; ordinary/legacy materials with no metadata are unchanged.
 */
export function restoreNativeMaterialProperties(root) {
  root.traverse(object => {
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      const color = material?.userData?.drenovarNativeBaseColor;
      if (!Array.isArray(color) || color.length !== 4 || !color.every(Number.isFinite)) continue;
      material.color.setRGB(color[0], color[1], color[2]);
      material.opacity = color[3];
      material.needsUpdate = true;
    }
  });
  return root;
}
