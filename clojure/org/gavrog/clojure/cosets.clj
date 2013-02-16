(ns org.gavrog.clojure.cosets
  (:use (org.gavrog.clojure
          free-word
          partition
          util)))

(defn- merge-rows [table equiv q a b]
  (let [merge (fn [ra rb]
                (reduce (fn [r g] (if (ra g) r (assoc r g (rb g))))
                        ra (keys rb)))
        row-a (merge (table a) (table b))
        row-b (merge (table b) (table a))
        q (into q (for [g (keys row-a)
                        :when (not= (equiv (row-a g)) (equiv (row-b g)))]
                    [(row-a g) (row-b g)]))
        table (conj table [a row-a] [b row-a])]
    [table q]))

(defn- identify [table equiv i j]
  (loop [q (conj empty-queue [i j])
         table table
         equiv equiv]
    (if-let [[i j] (first q)]
      (let [q (pop q)
            a (equiv i)
            b (equiv j)]
        (if (= a b)
          (recur q table equiv)
          (let [equiv (conj equiv [a b])
                [table q] (merge-rows table equiv q a b)]
            (recur q table equiv))))
      [table equiv])))

(defn- scan [table equiv w start]
  (let [n (count w)
        [head a] (loop [row start, i 0]
                   (if (>= i n)
                     [row i]
                     (if-let [next ((table row) (get w i))]
                       (recur next (inc i))
                       [row i])))
        [tail b] (loop [row start, i n]
                   (if (<= i a)
                     [row i]
                     (if-let [next ((table row) (- (get w (dec i))))]
                       (recur next (dec i))
                       [row i])))]
    (cond (= (inc a) b)
          [(-> table
             (assoc-in [head (get w a)] tail)
             (assoc-in [tail (- (get w a))] head))
           equiv]
          
          (and (= a b) (not= head tail))
          (identify table equiv head tail)
          
          :else
          [table equiv])))

(defn- scan-relations [rels subgens table equiv n]
  (let [[table equiv]
        (reduce (fn [[t p] w] (scan t p w n)) [table equiv] rels)]
    (reduce (fn [[t p] w] (scan t p w (equiv 0))) [table equiv] subgens)))

(defn- compressed-table [table equiv]
  (let [reps (into (sorted-set) (filter #(= % (equiv %)) (keys table)))
        rep-to-idx (into {} (map vector reps (range)))
        canon (comp rep-to-idx equiv)]
    (into {} (for [[i row] table :when (reps i)]
               [(canon i) (into {} (map (fn [[j v]] [j (canon v)]) row))]))))

(defn- maybe-compressed [[table equiv] factor]
  (let [nr-invalid (- (reduce + (map count equiv)) (count equiv))]
    (if (> nr-invalid (* factor (count table)))
      (compressed-table [table equiv])
      [table equiv])))

(defn coset-table [nr-gens relators subgroup-gens]
  (let [with-inverses (fn [ws] (vec (into #{} (concat ws (map inverse ws)))))
        gens (vec (concat (range 1 (inc nr-gens))
                          (range -1 (- (inc nr-gens)) -1)))
        rels (with-inverses (for [w relators, i (range (count w))]
                              (into (subvec w i) (subvec w 0 i))))
        subgens (with-inverses subgroup-gens)]
    (loop [table {0 {}}
           equiv pempty
           i 0
           j 0]
      (assert (< (count table) 500))
      (cond (>= i (count table))
            (compressed-table table equiv)
            
            (or (>= j (count gens)) (not= i (equiv i)))
            (recur table equiv (inc i) 0)
            
            ((table i) (get gens j))
            (recur table equiv i (inc j))
            
            :else
            (let [g (get gens j)
                  g* (- g)
                  n (count table)
                  table (-> table (assoc-in [i g] n) (assoc-in [n g*] i))
                  [table equiv] (maybe-compressed
                                  (scan-relations rels subgens table equiv n)
                                  1/2)]
              (recur table equiv i (inc j)))))))

(defn coset-representatives [table]
  (loop [q (conj empty-queue 0)
         reps {0 []}]
    (if-let [i (first q)]
      (let [row (table i)
            free (filter (comp nil? reps second) row)
            reps (into reps (map (fn [[g k]] [k (-* (reps i) [g])]) free))
            q (into (pop q) (map second free))]
        (recur q reps))
      reps)))