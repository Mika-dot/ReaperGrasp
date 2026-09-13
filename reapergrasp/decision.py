import math

CLASSES=['connection','foreign','garbage','point','normal']


def decide(probabilities, detections, threshold=.7):
    if probabilities is None:
        return dict(state='warming_up',probability=None,label=None,reason='insufficient_history')
    if len(probabilities)!=5 or any(not math.isfinite(v) or v<0 or v>1 for v in probabilities) or abs(sum(probabilities)-1)>1e-4:
        raise ValueError('Invalid model probabilities')
    label=CLASSES[max(range(5),key=probabilities.__getitem__)]
    score=1-probabilities[4]
    if score>=threshold:
        state='defect';reason='temporal_defect'
    elif detections:
        state='review';reason='yolo_temporal_disagreement'
    else:
        state='normal';reason='no_detection_below_threshold'
    return dict(state=state,probability=score,label=label,reason=reason)
