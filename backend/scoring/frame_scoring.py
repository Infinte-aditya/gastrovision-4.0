import json
import os
import paths
from typing import List
from operator import itemgetter

class frame_scoring:

    def filter_low_confidence(self,video_name, conf_threshold):

        score_arr =[]
        count = 0
        total_count =0

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_dir = os.path.join(paths.outputs_dir(), video_name)

        with open(f"{video_dir}/frame_scores.jsonl","r") as file:
            for line in file:
                output = json.loads(line)
                confidence = output.get('confidence')
                frame = output.get('frame')
                label = output.get('label')
                probabilities = output.get('probabilities')
                total_count += 1
                if confidence is None:
                    continue
                if confidence >= conf_threshold and not output.get('is_other', False):
                    count += 1
                    score_arr.append(output)

        removed_count = total_count - count

        return score_arr,removed_count,total_count



    def rank_frames(self,score_arr):

        # sorted_frames = sorted(
        #     score_arr,
        #     key=lambda  x: x["confidence"],
        #     reverse=True
        # )

        sorted_frames = sorted(score_arr, key=itemgetter('confidence'), reverse=True)

        ranked = []

        for i,frame in enumerate(sorted_frames):
            new_frame = frame.copy()
            new_frame['rank'] = i + 1
            new_frame['score'] = frame["confidence"]

            ranked.append(new_frame)

        return ranked


    def compute_stats(self,video_name,conf_threshold):

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_dir = os.path.join(paths.outputs_dir(), video_name)
        frame_ranked= os.path.join(video_dir,"frame_ranked.json")


        score_arr,removed_count,total_count = self.filter_low_confidence(video_name, conf_threshold)
        ranked_frames = self.rank_frames(score_arr)

        final_count = len(ranked_frames)

        total_conf = 0

        for frame in ranked_frames:
            total_conf = total_conf + frame['confidence']

        if final_count != 0:
            avg_confidence = total_conf/final_count
            top_label = ranked_frames[0]['label']
        else:
            avg_confidence = 0
            top_label = None

        
        result = {
        "ranked_frames": ranked_frames,
        "stats": {
            "total_input": total_count,
            "low_confidence_removed": removed_count,
            "final_ranked": final_count,
            "top_label": top_label,
            "average_confidence": avg_confidence
        }
    }

        with open(frame_ranked,"w") as file:
            json.dump(result,file,indent=4)

        return result
