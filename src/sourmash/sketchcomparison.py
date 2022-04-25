"""
Sketch Comparison Classes
"""
import numpy as np
from dataclasses import dataclass

from .signature import MinHash


@dataclass
class BaseMinHashComparison:
    """Class for standard comparison between two MinHashes"""
    mh1: MinHash
    mh2: MinHash
    ignore_abundance: bool = False # optionally ignore abundances

    def downsample_and_handle_ignore_abundance(self, cmp_num=None, cmp_scaled=None):
        """
        Downsample and/or flatten minhashes for comparison
        """
        if self.ignore_abundance:
            self.mh1_cmp = self.mh1.flatten()
            self.mh2_cmp = self.mh2.flatten()
        else:
            self.mh1_cmp = self.mh1
            self.mh2_cmp = self.mh2
        if cmp_scaled is not None:
            self.mh1_cmp = self.mh1_cmp.downsample(scaled=cmp_scaled)
            self.mh2_cmp = self.mh2_cmp.downsample(scaled=cmp_scaled)
        elif cmp_num is not None:
            self.mh1_cmp = self.mh1_cmp.downsample(num=cmp_num)
            self.mh2_cmp = self.mh2_cmp.downsample(num=cmp_num)
        else:
            raise ValueError("Error: must pass in a comparison scaled or num value.")

    def check_compatibility_and_downsample(self, cmp_num=None, cmp_scaled=None):
        if not any([(self.mh1.num and self.mh2.num), (self.mh1.scaled and self.mh2.scaled)]):
            raise TypeError("Error: Both sketches must be 'num' or 'scaled'.")

        #need to downsample first because is_compatible checks scaled (though does not check num)
        self.downsample_and_handle_ignore_abundance(cmp_num=cmp_num, cmp_scaled=cmp_scaled)
        if not self.mh1_cmp.is_compatible(self.mh2_cmp):
            raise TypeError("Error: Cannot compare incompatible sketches.")
        self.ksize = self.mh1.ksize
        self.moltype = self.mh1.moltype

    @property
    def intersect_mh(self):
        # flatten and intersect
        return self.mh1_cmp.flatten().intersection(self.mh2_cmp.flatten())

    @property
    def jaccard(self):
        return self.mh1_cmp.jaccard(self.mh2_cmp)

    @property
    def jaccard_ani(self):
        return self.mh1_cmp.jaccard_ani(self.mh2_cmp)

    @property
    def angular_similarity(self):
        # Note: this currently throws TypeError if self.ignore_abundance.
        return self.mh1_cmp.angular_similarity(self.mh2_cmp)

    @property
    def cosine_similarity(self):
        return self.angular_similarity


@dataclass
class NumMinHashComparison(BaseMinHashComparison):
    """Class for standard comparison between two num minhashes"""
    cmp_num: int = None

    def __post_init__(self):
        "Initialize NumMinHashComparison using values from provided MinHashes"
        if self.cmp_num is None: # record the num we're doing this comparison on
            self.cmp_num = min(self.mh1.num, self.mh2.num)
        self.check_compatibility_and_downsample(cmp_num=self.cmp_num)

@dataclass
class FracMinHashComparison(BaseMinHashComparison):
    """Class for standard comparison between two scaled minhashes"""
    cmp_scaled: int = None # optionally force scaled value for this comparison
    threshold_bp: int = 0
    estimate_ani_ci: bool = False
    ani_confidence: int = 0.95

    def __post_init__(self):
        "Initialize ScaledComparison using values from provided FracMinHashes"
        if self.cmp_scaled is None:
            # comparison scaled defaults to maximum scaled between the two sigs
            self.cmp_scaled = max(self.mh1.scaled, self.mh2.scaled)
        self.check_compatibility_and_downsample(cmp_scaled=self.cmp_scaled)

    @property
    def pass_threshold(self):
        return self.intersect_bp >= self.threshold_bp

    @property
    def intersect_bp(self):
        return len(self.intersect_mh) * self.cmp_scaled

    @property
    def mh1_containment(self):
        return self.mh1_cmp.contained_by(self.mh2_cmp)

    @property
    def mh1_containment_ani(self):
        return self.mh1_cmp.containment_ani(self.mh2_cmp,
                                            confidence=self.ani_confidence,
                                            estimate_ci=self.estimate_ani_ci)

    @property
    def mh2_containment(self):
        return self.mh2_cmp.contained_by(self.mh1_cmp)

    @property
    def mh2_containment_ani(self):
        return self.mh2_cmp.containment_ani(self.mh1_cmp,
                                            confidence=self.ani_confidence,
                                            estimate_ci=self.estimate_ani_ci)

    @property
    def max_containment(self):
        return self.mh1_cmp.max_containment(self.mh2_cmp)

    @property
    def max_containment_ani(self):
        return self.mh1_cmp.max_containment_ani(self.mh2_cmp,
                                                confidence=self.ani_confidence,
                                                estimate_ci=self.estimate_ani_ci)

    @property
    def avg_containment(self):
        return np.mean([self.mh1_containment, self.mh2_containment])

    @property
    def avg_containment_ani(self):
        "Returns single average_containment_ani value."
        return np.mean([self.mh1_containment_ani.ani, self.mh2_containment_ani.ani])

    def weighted_intersection(self, from_mh=None, from_abundD={}):
         # map abundances to all intersection hashes.
        abund_mh = self.intersect_mh.copy_and_clear()
        abund_mh.track_abundance = True
        # if from_mh is provided, it takes precedence over from_abund dict
        if from_mh is not None and from_mh.track_abundance:
            from_abundD = from_mh.hashes
        if from_abundD:
            # this sets any hash not present in abundD to 1. Is that desired? Or should we return 0?
            abunds = {k: from_abundD.get(k, 1) for k in self.intersect_mh.hashes }
            abund_mh.set_abundances(abunds)
            return abund_mh
        # if no abundances are passed in, return intersect_mh
        # future note: do we want to return 1 as abundance instead?
        return self.intersect_mh