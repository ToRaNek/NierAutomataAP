#ifndef NIER_AP_OVERLAY_H
#define NIER_AP_OVERLAY_H
#include <stdint.h>

#define OVERLAY_MAX_WALLS 8

#pragma pack(push, 1)
typedef struct {
    float x1, y, z1;      /* pied du mur, premiere extremite */
    float x2, z2;         /* seconde extremite (meme hauteur de sol) */
    float height;
    char text[64];        /* texte affiche sur le bandeau, termine par 0 */
} overlay_wall_t;
#pragma pack(pop)

void overlay_start(void);
/* eye / target / fov : adresses absolues de la camera du jeu (vec3, vec3, float en radians) */
void overlay_set(const overlay_wall_t *walls, int count, uint64_t eye, uint64_t target, uint64_t fov);
int overlay_status(void);   /* 1 pret, 0 pas encore dessine, -1 echec */

#endif
