"""Two full rotations while briefly shrinking and growing back."""

from ida_frustrated_core import register_effect


def _paint(painter, snapshot, rect, progress, overlay):
    overlay.erase_original(painter, rect)

    transition = 1.0 - progress
    smallest = 0.5
    if transition > smallest:
        shrinkage = transition
    elif transition < (1.0 - smallest):
        shrinkage = 1.0 - transition
    else:
        shrinkage = smallest

    biggest = min(rect.width(), rect.height())
    max_shrink = biggest * 0.50
    offset = int(max_shrink - (max_shrink * shrinkage))
    transformed_rect = rect.adjusted(offset, offset, -offset, -offset)
    center = transformed_rect.center()

    painter.save()
    painter.translate(center)
    painter.rotate(360.0 * 2.0 * progress)
    painter.translate(-center)
    painter.drawPixmap(transformed_rect, snapshot)
    painter.restore()


register_effect("rotate", 1000, _paint)
