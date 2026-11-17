"""Skeleton definition, forward kinematics and leg IK.

Rest rotations are identity for every joint: a joint's rest local transform is
a pure translation (its rest world head minus its parent's). Local animation
rotations are therefore expressed directly in the creature frame (+X forward,
+Y up, +Z right), which keeps authored angles readable.
"""
import numpy as np

from qmath import q_identity, q_mul, q_conj, q_rotate, q_between, q_axis, q_normalize


class Bone:
    def __init__(self, name, parent, head, deform=True, tail=None):
        self.name, self.parent, self.deform = name, parent, deform
        self.head = np.asarray(head, float)
        self.tail = None if tail is None else np.asarray(tail, float)


class Skeleton:
    def __init__(self):
        self.bones = []
        self.by = {}
        self.sockets = []  # (name, bone, world position at rest)

    def add(self, name, parent, head, deform=True, tail=None):
        if parent is not None and parent not in self.by:
            raise KeyError(parent)
        b = Bone(name, parent, head, deform, tail)
        self.by[name] = len(self.bones)
        self.bones.append(b)
        return b

    def socket(self, name, bone, pos):
        self.sockets.append((name, bone, np.asarray(pos, float)))

    def bone(self, name):
        return self.bones[self.by[name]]

    def children(self, name):
        return [b for b in self.bones if b.parent == name]

    def rest_offset(self, name):
        b = self.bone(name)
        return b.head - (self.bone(b.parent).head if b.parent else np.zeros(3))

    def tail_of(self, name):
        b = self.bone(name)
        if b.tail is not None:
            return b.tail
        kids = self.children(name)
        if kids:
            return np.mean([k.head for k in kids if k.deform] or [k.head for k in kids], axis=0)
        return b.head + np.array([0.05, 0, 0])

    def deform_names(self):
        return [b.name for b in self.bones if b.deform]

    def fk(self, local_rot, local_off=None):
        """World (position, rotation) for every bone from local rotations (dict) and extra translations."""
        pos, rot = {}, {}
        for b in self.bones:
            q = local_rot.get(b.name, q_identity())
            off = self.rest_offset(b.name) + (local_off.get(b.name, 0.0) if local_off else 0.0)
            if b.parent is None:
                pos[b.name] = off
                rot[b.name] = q
            else:
                pr = rot[b.parent]
                pos[b.name] = pos[b.parent] + q_rotate(pr, off)
                rot[b.name] = q_normalize(q_mul(pr, q))
        return pos, rot


def two_bone_ik(a, l1, l2, target, pole):
    """Positions of the middle joint for a two-segment chain from a to target, bending toward pole."""
    d = target - a
    dist = np.linalg.norm(d)
    dist_c = np.clip(dist, abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
    dn = d / max(dist, 1e-9)
    # angle at a between chain and upper segment
    cos_a = (l1 * l1 + dist_c * dist_c - l2 * l2) / (2 * l1 * dist_c)
    cos_a = np.clip(cos_a, -1, 1)
    sin_a = np.sqrt(1 - cos_a * cos_a)
    p = pole - a
    p = p - np.dot(p, dn) * dn
    pn = np.linalg.norm(p)
    if pn < 1e-9:
        p = np.cross(dn, (0, 0, 1))
        pn = np.linalg.norm(p)
    p /= pn
    mid = a + dn * (cos_a * l1) + p * (sin_a * l1)
    end = a + dn * dist_c
    return mid, end, dist > l1 + l2 - 1e-3


def aim_local(skel, name, parent_rot, child_name, direction, twist_axis=None):
    """Local rotation for bone `name` so its child joint lies along world `direction`."""
    rest = skel.rest_offset(child_name)
    want = q_rotate(q_conj(parent_rot), direction)
    return q_between(rest, want)
