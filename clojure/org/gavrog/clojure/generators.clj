(ns org.gavrog.clojure.generators)

(defprotocol SubstepGenerator
  (result [_])
  (step [_]))

(defn traverse [gen]
  (when gen
    (if-let [next (step gen)]
      (lazy-seq (cons gen (traverse next)))
      (list gen))))

(defn results [gen]
  (remove nil? (map result (traverse gen))))

(defprotocol SplittableGenerator
  (sub-generator [_])
  (skip [_]))

(defprotocol Resumable
  (checkpoint [_])
  (resume [_ checkpoint]))

(deftype BacktrackingGenerator [extract make-children stack]
  SubstepGenerator
  (result [_] (extract (first (first stack))))
  (step [gen]
        (if-let [children (seq (make-children (first (first stack))))]
          (let [stack (conj stack [(first children) (rest children) 0])]
            (BacktrackingGenerator. extract make-children stack))
          (skip gen)))
  Resumable
  (checkpoint [_] (rest (reverse (map #(nth % 2) stack))))
  (resume [_ checkpoint]
          (loop [todo checkpoint
                 stack stack]
            (if (seq todo)
              (let [n (first todo)
                    children (drop n (make-children (first (first stack))))
                    stack (conj stack [(first children) (rest children) n])]
                (recur (rest todo) stack))
              (BacktrackingGenerator. extract make-children stack))))
  SplittableGenerator
  (sub-generator [gen]
                 (let [stack (list [(first (first stack)) nil 0])]
                   (BacktrackingGenerator. extract make-children stack)))
  (skip [_]
        (when-let [stack (seq (drop-while #(empty? (second %)) stack))]
          (let [[node siblings-left branch-nr] (first stack)
                stack (conj (rest stack)
                            [(first siblings-left)
                             (rest siblings-left)
                             (inc branch-nr)])]
            (BacktrackingGenerator. extract make-children stack)))))

(defn make-backtracker [spec]
  (BacktrackingGenerator. (:extract spec)
                          (:children spec)
                          (list [(:root spec) nil 0])))

