class SkinProfile:
    def __init__(
        self,
        age,

        # Acne / clogged pores
        inflammatory_acne,
        blackheads,
        whiteheads,

        # Post-acne marks / pigmentation
        pie,
        pih,

        # Redness / inflammation
        redness,
        rosacea,

        # Skin barrier / irritation
        dryness,
        sensitivity,
        irritation,

        # Oil production
        oiliness,

        # Texture
        texture_irregularity,
        acne_scarring,

        # Other common concerns
        enlarged_pores,
        dark_circles,
        uneven_skin_tone,
    ):
        self.age = age

        self.inflammatory_acne = inflammatory_acne
        self.blackheads = blackheads
        self.whiteheads = whiteheads

        self.pie = pie
        self.pih = pih

        self.redness = redness
        self.rosacea = rosacea

        self.dryness = dryness
        self.sensitivity = sensitivity
        self.irritation = irritation

        self.oiliness = oiliness

        self.texture_irregularity = texture_irregularity
        self.acne_scarring = acne_scarring

        self.enlarged_pores = enlarged_pores
        self.dark_circles = dark_circles
        self.uneven_skin_tone = uneven_skin_tone

    def get_skin_summary(self):
        return {
            "age": self.age,

            "acne" : {
                "inflammatory_acne": self.inflammatory_acne,
                "blackheads": self.blackheads,
                "whiteheads": self.whiteheads,
            },
            
            "pigmentation" : {
                "pie": self.pie,
                "pih": self.pih,
            },
            
            "appearance" : {
                "redness": self.redness,
                "rosacea": self.rosacea,
                "dark_circles": self.dark_circles,
                "uneven_skin_tone": self.uneven_skin_tone
            },

            "barrier" : {
                "dryness": self.dryness,
                "sensitivity": self.sensitivity,
                "irritation": self.irritation,
                "oiliness": self.oiliness,
            },
            
            "texture" : {
                "texture_irregularity": self.texture_irregularity,
                "acne_scarring": self.acne_scarring,
                "enlarged_pores": self.enlarged_pores,
            },
        }